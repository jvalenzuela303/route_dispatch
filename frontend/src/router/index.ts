import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import type { RoleName } from '@/types'

// Lazy load views
const LoginView = () => import('@/views/auth/LoginView.vue')
const DashboardView = () => import('@/views/dashboard/DashboardView.vue')

// Orders
const OrdersListView = () => import('@/views/orders/OrdersListView.vue')
const OrderCreateView = () => import('@/views/orders/OrderCreateView.vue')
const OrderDetailView = () => import('@/views/orders/OrderDetailView.vue')

// Routes
const RoutesListView = () => import('@/views/routes/RoutesListView.vue')
const RouteGenerateView = () => import('@/views/routes/RouteGenerateView.vue')
const RouteDetailView = () => import('@/views/routes/RouteDetailView.vue')
const RouteTrackingView = () => import('@/views/routes/RouteTrackingView.vue')

// Users
const UsersListView = () => import('@/views/users/UsersListView.vue')
const UserCreateView = () => import('@/views/users/UserCreateView.vue')
const UserEditView = () => import('@/views/users/UserEditView.vue')

// Reports
const ReportsView = () => import('@/views/reports/ReportsView.vue')
const AuditLogsView = () => import('@/views/reports/AuditLogsView.vue')

// Vehicles
const VehiclesListView = () => import('@/views/vehicles/VehiclesListView.vue')
const VehicleFormView = () => import('@/views/vehicles/VehicleFormView.vue')

// Fleet / GPS
const LiveMapView = () => import('@/views/fleet/LiveMapView.vue')

// Layout
const MainLayout = () => import('@/components/common/MainLayout.vue')

declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: RoleName[]
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'login',
    component: LoginView,
    meta: { title: 'Iniciar Sesión' },
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'dashboard',
        component: DashboardView,
        meta: { title: 'Dashboard' },
      },
      // Orders routes
      {
        path: 'orders',
        name: 'orders',
        component: OrdersListView,
        meta: {
          title: 'Pedidos',
          roles: ['Administrador', 'Encargado de Bodega', 'Vendedor'],
        },
      },
      {
        path: 'orders/create',
        name: 'orders-create',
        component: OrderCreateView,
        meta: {
          title: 'Nuevo Pedido',
          roles: ['Administrador', 'Encargado de Bodega', 'Vendedor'],
        },
      },
      {
        path: 'orders/:id',
        name: 'orders-detail',
        component: OrderDetailView,
        meta: {
          title: 'Detalle de Pedido',
          roles: ['Administrador', 'Encargado de Bodega', 'Vendedor', 'Repartidor'],
        },
      },
      // Routes management
      {
        path: 'routes',
        name: 'routes',
        component: RoutesListView,
        meta: {
          title: 'Rutas',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      {
        path: 'routes/generate',
        name: 'routes-generate',
        component: RouteGenerateView,
        meta: {
          title: 'Generar Ruta',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      {
        path: 'routes/:id',
        name: 'routes-detail',
        component: RouteDetailView,
        meta: {
          title: 'Detalle de Ruta',
          roles: ['Administrador', 'Encargado de Bodega', 'Repartidor'],
        },
      },
      {
        path: 'tracking',
        name: 'tracking',
        component: RouteTrackingView,
        meta: {
          title: 'Mis Entregas',
          roles: ['Repartidor'],
        },
      },
      // Users management
      {
        path: 'users',
        name: 'users',
        component: UsersListView,
        meta: {
          title: 'Usuarios',
          roles: ['Administrador'],
        },
      },
      {
        path: 'users/create',
        name: 'users-create',
        component: UserCreateView,
        meta: {
          title: 'Nuevo Usuario',
          roles: ['Administrador'],
        },
      },
      {
        path: 'users/:id/edit',
        name: 'users-edit',
        component: UserEditView,
        meta: {
          title: 'Editar Usuario',
          roles: ['Administrador'],
        },
      },
      // Vehicles
      {
        path: 'vehicles',
        name: 'vehicles',
        component: VehiclesListView,
        meta: {
          title: 'Vehículos',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      {
        path: 'vehicles/create',
        name: 'vehicles-create',
        component: VehicleFormView,
        meta: {
          title: 'Nuevo Vehículo',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      {
        path: 'vehicles/:id/edit',
        name: 'vehicles-edit',
        component: VehicleFormView,
        meta: {
          title: 'Editar Vehículo',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      // Fleet / GPS live map
      {
        path: 'fleet',
        name: 'fleet',
        component: LiveMapView,
        meta: {
          title: 'Mapa en Vivo',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      // Reports
      {
        path: 'reports',
        name: 'reports',
        component: ReportsView,
        meta: {
          title: 'Reportes',
          roles: ['Administrador', 'Encargado de Bodega'],
        },
      },
      {
        path: 'audit-logs',
        name: 'audit-logs',
        component: AuditLogsView,
        meta: {
          title: 'Auditoría',
          roles: ['Administrador'],
        },
      },
    ],
  },
  // Catch all - redirect to dashboard
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guards
router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // Update page title
  document.title = to.meta.title
    ? `${to.meta.title} | Logistics`
    : 'Logistics'

  // Check if route requires authentication
  if (to.meta.requiresAuth || to.matched.some((record) => record.meta.requiresAuth)) {
    const isAuthenticated = await authStore.checkAuth()

    if (!isAuthenticated) {
      return next({ name: 'login', query: { redirect: to.fullPath } })
    }

    // Check role-based access
    const requiredRoles = to.meta.roles || to.matched.find((r) => r.meta.roles)?.meta.roles

    if (requiredRoles && requiredRoles.length > 0) {
      if (!authStore.hasRole(requiredRoles)) {
        // Redirect to dashboard if user doesn't have required role
        return next({ name: 'dashboard' })
      }
    }
  }

  // Redirect to dashboard if already authenticated and trying to access login
  if (to.name === 'login') {
    const isAuthenticated = await authStore.checkAuth()
    if (isAuthenticated) {
      return next({ name: 'dashboard' })
    }
  }

  next()
})

export default router
