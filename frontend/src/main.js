import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { loadAuthState } from './stores/auth'
import { loadTheme } from './stores/theme'
import { setupAuthInterceptor } from './utils/api'
import './styles.css'

loadAuthState()
loadTheme()
setupAuthInterceptor(router)

const app = createApp(App)
app.use(router)
app.mount('#app')
