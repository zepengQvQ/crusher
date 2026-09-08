import { createRouter, createWebHistory } from 'vue-router'
import InputPage from '../pages/InputPage.vue'
import StatusPage from '../pages/StatusPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import ErrorPage from '../pages/ErrorPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'input', component: InputPage },
    { path: '/status/:taskId', name: 'status', component: StatusPage, props: true },
    { path: '/report/:taskId', name: 'report', component: ReportPage, props: true },
    { path: '/error', name: 'error', component: ErrorPage },
  ],
})

export default router
