import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import './styles/main.css'
import './styles/auth.css'
import './styles/code.css'

createApp(App).use(router).mount('#app')
