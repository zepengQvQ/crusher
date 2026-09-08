import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  Button,
  Cell,
  CellGroup,
  Collapse,
  CollapseItem,
  Empty,
  Field,
  NavBar,
  NoticeBar,
  Picker,
  Popup,
  Skeleton,
  Tag,
  showToast,
} from 'vant'
import 'vant/lib/index.css'

import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(createPinia())
app.use(router)
;[
  Button,
  Cell,
  CellGroup,
  Collapse,
  CollapseItem,
  Empty,
  Field,
  NavBar,
  NoticeBar,
  Picker,
  Popup,
  Skeleton,
  Tag,
].forEach((c) => app.use(c))
app.config.globalProperties.$toast = showToast
app.mount('#app')
