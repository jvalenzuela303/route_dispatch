"""
Route optimization service using Google OR-Tools

Implements:
- TSP (Traveling Salesperson Problem) solver for single-vehicle routes
- PostGIS-based distance matrix calculation
- Route generation from DOCUMENTADO orders
- Integration with OrderService for EN_RUTA transition

Business Rules:
- BR-024: Route optimization must complete for 50 orders in < 10 seconds
- BR-025: Routes can only include DOCUMENTADO orders with invoices and coordinates
- BR-026: Activating route transitions all included orders to EN_RUTA status
"""

import uuid
from typing import List, Optional, Dict, Tuple
from datetime import date, datetime, timezone
from decimal import Decimal
import numpy as np

from sqlalchemy import text, func
from sqlalchemy.orm import Session
from ortools.constraint_solver import routing_enums_pb2
from ortools.constraint_solver import pywrapcp

from app.models.models import Order, Route, User
from app.models.enums import OrderStatus, RouteStatus, AuditResult
from app.services.audit_service import AuditService
from app.config.settings import get_settings
from app.exceptions import RouteOptimizationError, ValidationError


class RouteOptimizationService:
    """
    Service for route optimization using Google OR-Tools

    Solves TSP (Traveling Salesperson Problem) to minimize
    total distance for delivery routes
    """

    def __init__(self, db: Session):
        """
        Initialize route optimization service

        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.audit_service = AuditService(db)
        self.settings = get_settings()

        # Depot (warehouse) coordinates
        self.depot_lat = self.settings.depot_latitude
        self.depot_lon = self.settings.depot_longitude

        # Route optimization parameters
        self.avg_speed_kmh = self.settings.average_speed_kmh
        self.service_time_minutes = self.settings.service_time_per_stop_minutes
        self.optimization_timeout = self.settings.route_optimization_timeout_seconds

    def generate_route_for_date(
        self,
        delivery_date: date,
        user: User
    ) -> Route:
        """
        Generate optimized route for a delivery date

        Steps:
        1. Fetch eligible orders (DOCUMENTADO status with delivery_date)
        2. Validate orders have invoices and coordinates
        3. Extract coordinates (depot + orders)
        4. Calculate distance matrix using PostGIS
        5. Solve TSP with OR-Tools
        6. Create Route with optimized stop_sequence
        7. Calculate total distance and estimated duration
        8. Create audit log

        Args:
            delivery_date: Target delivery date
            user: User generating the route (Encargado/Admin)

        Returns:
            Route: Created optimized route

        Raises:
            RouteOptimizationError: If no eligible orders or optimization fails
        """

        # 1. Fetch eligible orders
        orders = self._get_orders_for_routing(delivery_date)

        if not orders:
            raise RouteOptimizationError(
                f"No hay pedidos documentados para {delivery_date}",
                details={
                    "delivery_date": str(delivery_date),
                    "required_status": OrderStatus.DOCUMENTADO.value
                }
            )

        # 2. Validate orders
        self._validate_orders_for_routing(orders)

        # 3. Extract coordinates
        coordinates = self._extract_coordinates(orders)

        # 4. Calculate distance matrix
        distance_matrix = self._calculate_distance_matrix(coordinates)

        # 5. Solve TSP
        solution = self._solve_tsp(distance_matrix)

        if not solution:
            raise RouteOptimizationError(
                "No se pudo encontrar solución óptima para la ruta",
                details={
                    "num_orders": len(orders),
                    "timeout_seconds": self.optimization_timeout
                }
            )

        # 6. Extract optimized sequence
        stop_sequence = self._extract_stop_sequence(solution, orders)

        # 7. Calculate metrics
        total_distance_km = self._calculate_total_distance(solution)
        estimated_duration_minutes = self._estimate_duration(
            total_distance_km, len(orders)
        )

        # 8. Create Route
        route = self._create_route(
            delivery_date=delivery_date,
            stop_sequence=stop_sequence,
            total_distance_km=total_distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            user=user
        )

        # 9. Audit log
        self.audit_service.log_action(
            user=user,
            action="GENERATE_ROUTE",
            entity_type="ROUTE",
            entity_id=route.id,
            details={
                "delivery_date": str(delivery_date),
                "num_orders": len(orders),
                "total_distance_km": float(total_distance_km),
                "estimated_duration_minutes": estimated_duration_minutes,
                "optimization_method": "TSP_OR_TOOLS"
            },
            result=AuditResult.SUCCESS
        )

        return route

    def activate_route(
        self,
        route_id: uuid.UUID,
        driver_id: uuid.UUID,
        user: User
    ) -> Route:
        """
        Activate a route (DRAFT to ACTIVE) and assign to driver

        Steps:
        1. Fetch route and validate status
        2. Assign driver
        3. Change status to ACTIVE
        4. Transition all orders to EN_RUTA
        5. Set started_at timestamp
        6. Audit log

        Args:
            route_id: Route UUID
            driver_id: Driver user UUID
            user: User activating route (Encargado/Admin)

        Returns:
            Route: Activated route

        Raises:
            RouteOptimizationError: If route not found or invalid status
            ValidationError: If driver not found
        """
        # 1. Fetch route
        route = self.db.query(Route).filter(Route.id == route_id).first()

        if not route:
            raise RouteOptimizationError(
                f"Ruta {route_id} no encontrada",
                details={"route_id": str(route_id)}
            )

        if route.status != RouteStatus.DRAFT:
            raise RouteOptimizationError(
                f"Ruta debe estar en DRAFT, está en {route.status.value}",
                details={
                    "route_id": str(route_id),
                    "current_status": route.status.value,
                    "required_status": RouteStatus.DRAFT.value
                }
            )

        # Validate driver exists
        driver = self.db.query(User).filter(User.id == driver_id).first()
        if not driver:
            raise ValidationError(
                code="DRIVER_NOT_FOUND",
                message=f"Repartidor {driver_id} no encontrado",
                details={"driver_id": str(driver_id)}
            )

        # 2. Assign driver and update status
        route.assigned_driver_id = driver_id
        route.status = RouteStatus.ACTIVE
        route.started_at = datetime.now(timezone.utc)

        # 3. Transition orders to EN_RUTA
        order_ids = route.stop_sequence or []
        for order_id in order_ids:
            order = self.db.query(Order).filter(
                Order.id == uuid.UUID(order_id) if isinstance(order_id, str) else order_id
            ).first()

            if order:
                order.order_status = OrderStatus.EN_RUTA
                order.assigned_route_id = route.id

        self.db.commit()
        self.db.refresh(route)

        # 4. Audit log
        self.audit_service.log_action(
            user=user,
            action="ACTIVATE_ROUTE",
            entity_type="ROUTE",
            entity_id=route.id,
            details={
                "driver_id": str(driver_id),
                "driver_username": driver.username,
                "num_orders": len(order_ids),
                "route_name": route.route_name
            },
            result=AuditResult.SUCCESS
        )

        return route

    def _get_orders_for_routing(self, delivery_date: date) -> List[Order]:
        """
        Get eligible orders for routing

        Criteria:
        - status = DOCUMENTADO
        - delivery_date = specified date
        - invoice_id IS NOT NULL (guaranteed by DOCUMENTADO status)
        - address_coordinates IS NOT NULL

        Args:
            delivery_date: Target delivery date

        Returns:
            List[Order]: Eligible orders
        """
        orders = self.db.query(Order).filter(
            Order.order_status == OrderStatus.DOCUMENTADO,
            Order.delivery_date == delivery_date,
            Order.invoice_id.isnot(None),
            Order.address_coordinates.isnot(None)
        ).all()

        return orders

    def _validate_orders_for_routing(self, orders: List[Order]) -> None:
        """
        Validate all orders are eligible for routing

        Args:
            orders: List of orders to validate

        Raises:
            RouteOptimizationError: If any order is invalid
        """
        for order in orders:
            # Check invoice
            if not order.invoice_id:
                raise RouteOptimizationError(
                    f"Pedido {order.order_number} no tiene factura",
                    details={
                        "order_id": str(order.id),
                        "order_number": order.order_number
                    }
                )

            # Check coordinates
            if not order.address_coordinates:
                raise RouteOptimizationError(
                    f"Pedido {order.order_number} no tiene coordenadas",
                    details={
                        "order_id": str(order.id),
                        "order_number": order.order_number
                    }
                )

    def _extract_coordinates(
        self,
        orders: List[Order]
    ) -> List[Tuple[float, float]]:
        """
        Extract coordinates: [depot, order1, order2, ...]

        Args:
            orders: List of orders with address_coordinates

        Returns:
            List of (latitude, longitude) tuples
        """
        # Start with depot
        coordinates = [(self.depot_lat, self.depot_lon)]

        # Extract coordinates from PostGIS geography
        for order in orders:
            # Use ST_Y for latitude, ST_X for longitude
            # address_coordinates is already in SRID 4326 (WGS84)
            lat = self.db.scalar(
                func.ST_Y(order.address_coordinates)
            )
            lon = self.db.scalar(
                func.ST_X(order.address_coordinates)
            )
            coordinates.append((lat, lon))

        return coordinates

    def _calculate_distance_matrix(
        self,
        coordinates: List[Tuple[float, float]]
    ) -> np.ndarray:
        """
        Calculate distance matrix using PostGIS ST_Distance

        Uses geography type for accurate distance calculation.
        Returns distances in meters as integers (required by OR-Tools).

        Args:
            coordinates: List of (latitude, longitude) tuples

        Returns:
            np.ndarray: N x N matrix with distances in meters (integers)
        """
        n = len(coordinates)
        matrix = np.zeros((n, n), dtype=int)

        for i in range(n):
            for j in range(n):
                if i == j:
                    matrix[i][j] = 0
                else:
                    lat_i, lon_i = coordinates[i]
                    lat_j, lon_j = coordinates[j]

                    # PostGIS ST_Distance with geography type
                    # Returns distance in meters
                    sql = text("""
                        SELECT ST_Distance(
                            ST_SetSRID(ST_MakePoint(:lon1, :lat1), 4326)::geography,
                            ST_SetSRID(ST_MakePoint(:lon2, :lat2), 4326)::geography
                        ) AS distance_meters
                    """)

                    result = self.db.execute(sql, {
                        "lon1": lon_i,
                        "lat1": lat_i,
                        "lon2": lon_j,
                        "lat2": lat_j
                    }).fetchone()

                    # Convert to integer meters for OR-Tools
                    matrix[i][j] = int(result.distance_meters)

        return matrix

    def _solve_tsp(self, distance_matrix: np.ndarray) -> Optional[Dict]:
        """
        Solve TSP using Google OR-Tools

        Args:
            distance_matrix: N x N matrix of distances (integers)

        Returns:
            Dict with 'route' (list of node indices) and 'total_distance' (int)
            None if no solution found
        """
        # Create routing index manager
        # num_nodes, num_vehicles, depot_index
        manager = pywrapcp.RoutingIndexManager(
            len(distance_matrix),  # Number of nodes
            1,                      # Number of vehicles (TSP = 1 vehicle)
            0                       # Depot index (always 0)
        )

        # Create routing model
        routing = pywrapcp.RoutingModel(manager)

        # Create distance callback
        def distance_callback(from_index: int, to_index: int) -> int:
            """Returns distance between two nodes"""
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)

        # Define cost of each arc
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        # Set search parameters
        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        search_parameters.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        search_parameters.time_limit.seconds = self.optimization_timeout

        # Solve the problem
        solution = routing.SolveWithParameters(search_parameters)

        if not solution:
            return None

        # Extract solution
        index = routing.Start(0)  # Start of route for vehicle 0
        route = []
        total_distance = 0

        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            route.append(node)
            previous_index = index
            index = solution.Value(routing.NextVar(index))
            total_distance += routing.GetArcCostForVehicle(
                previous_index, index, 0
            )

        # Add final node (return to depot)
        route.append(manager.IndexToNode(index))

        return {
            "route": route,
            "total_distance": total_distance  # in meters
        }

    def _extract_stop_sequence(
        self,
        solution: Dict,
        orders: List[Order]
    ) -> List[str]:
        """
        Extract sequence of order IDs from TSP solution

        Args:
            solution: Dict with 'route' (list of node indices)
            orders: List of orders (same order as coordinates - 1)

        Returns:
            List[str]: Sequence of order IDs as strings (for JSONB storage)
        """
        route = solution["route"]

        # Skip first (depot start) and last (depot end)
        # Node 0 = depot, Node 1 = orders[0], Node 2 = orders[1], ...
        stop_indices = route[1:-1]

        # Convert node indices to order IDs (as strings for JSONB)
        stop_sequence = [str(orders[idx - 1].id) for idx in stop_indices]

        return stop_sequence

    def _calculate_total_distance(self, solution: Dict) -> Decimal:
        """
        Calculate total distance in kilometers

        Args:
            solution: TSP solution with 'total_distance' in meters

        Returns:
            Decimal: Distance in kilometers (2 decimal places)
        """
        distance_meters = solution["total_distance"]
        distance_km = Decimal(distance_meters) / Decimal(1000)
        return round(distance_km, 2)

    def _estimate_duration(
        self,
        total_distance_km: Decimal,
        num_stops: int
    ) -> int:
        """
        Estimate total route duration

        Formula:
        - Travel time = distance / average_speed
        - Service time = num_stops × service_time_per_stop
        - Total = travel_time + service_time

        Args:
            total_distance_km: Total distance in kilometers
            num_stops: Number of delivery stops

        Returns:
            int: Estimated duration in minutes
        """
        # Travel time
        travel_hours = float(total_distance_km) / self.avg_speed_kmh
        travel_minutes = travel_hours * 60

        # Service time (time spent at each stop)
        service_minutes = num_stops * self.service_time_minutes

        # Total duration
        total_minutes = int(travel_minutes + service_minutes)

        return total_minutes

    def _create_route(
        self,
        delivery_date: date,
        stop_sequence: List[str],
        total_distance_km: Decimal,
        estimated_duration_minutes: int,
        user: User
    ) -> Route:
        """
        Create Route record in database

        Args:
            delivery_date: Delivery date
            stop_sequence: List of order IDs (as strings) in optimal order
            total_distance_km: Total route distance
            estimated_duration_minutes: Estimated duration
            user: User creating the route

        Returns:
            Route: Created route
        """
        # Generate route name
        route_count = self._get_route_count_for_date(delivery_date)
        route_name = f"Ruta {delivery_date.strftime('%Y-%m-%d')} #{route_count + 1}"

        route = Route(
            id=uuid.uuid4(),
            route_name=route_name,
            route_date=delivery_date,
            status=RouteStatus.DRAFT,  # DRAFT until activated
            stop_sequence=stop_sequence,  # JSONB array of order IDs
            total_distance_km=total_distance_km,
            estimated_duration_minutes=estimated_duration_minutes
        )

        self.db.add(route)
        self.db.commit()
        self.db.refresh(route)

        return route

    def _get_route_count_for_date(self, delivery_date: date) -> int:
        """
        Count existing routes for a delivery date

        Used for route numbering (e.g., "Ruta 2026-01-21 #1")

        Args:
            delivery_date: Delivery date

        Returns:
            int: Number of existing routes for this date
        """
        return self.db.query(Route).filter(
            Route.route_date == delivery_date
        ).count()

    def get_route_details(self, route_id: uuid.UUID) -> Dict:
        """
        Get detailed route information including ordered stops

        Args:
            route_id: Route UUID

        Returns:
            Dict with route details and ordered list of stops

        Raises:
            RouteOptimizationError: If route not found
        """
        route = self.db.query(Route).filter(Route.id == route_id).first()

        if not route:
            raise RouteOptimizationError(
                f"Ruta {route_id} no encontrada",
                details={"route_id": str(route_id)}
            )

        # Get ordered stops
        stops = []
        if route.stop_sequence:
            for idx, order_id_str in enumerate(route.stop_sequence, start=1):
                order_id = uuid.UUID(order_id_str)
                order = self.db.query(Order).filter(Order.id == order_id).first()

                if order:
                    stops.append({
                        "stop_number": idx,
                        "order_id": str(order.id),
                        "order_number": order.order_number,
                        "customer_name": order.customer_name,
                        "customer_phone": order.customer_phone,
                        "address_text": order.address_text,
                        "order_status": order.order_status.value
                    })

        return {
            "route_id": str(route.id),
            "route_name": route.route_name,
            "route_date": str(route.route_date),
            "status": route.status.value,
            "assigned_driver_id": str(route.assigned_driver_id) if route.assigned_driver_id else None,
            "total_distance_km": float(route.total_distance_km) if route.total_distance_km else None,
            "estimated_duration_minutes": route.estimated_duration_minutes,
            "actual_duration_minutes": route.actual_duration_minutes,
            "started_at": route.started_at.isoformat() if route.started_at else None,
            "completed_at": route.completed_at.isoformat() if route.completed_at else None,
            "num_stops": len(stops),
            "stops": stops
        }
