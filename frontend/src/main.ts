import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'
import 'md-editor-v3/lib/style.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
