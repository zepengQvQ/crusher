import { createRouter, createWebHistory } from 'vue-router'
import InputPage from '../pages/InputPage.vue'
import StatusPage from '../pages/StatusPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import ErrorPage from '../pages/ErrorPage.vue'
import DualInputPage from '../pages/DualInputPage.vue'
import DualReportPage from '../pages/DualReportPage.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'input', component: InputPage },
    { path: '/dual', name: 'dual-input', component: DualInputPage },
    { path: '/dual/report', name: 'dual-report', component: DualReportPage },
    { path: '/status/:taskId', name: 'status', component: StatusPage, props: true },
    { path: '/report/:taskId', name: 'report', component: ReportPage, props: true },
    {
      path: '/error/:taskId?',
      name: 'error',
      component: ErrorPage,
      props: true,
    },
  ],
})

export default router
