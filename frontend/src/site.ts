import { ref } from 'vue'
import { getPublicSite } from './api/client'

export const siteTitle = ref('C 语言学习笔记')
export const registrationEnabled = ref(true)

let siteLoaded = false

export async function loadSiteTitle(): Promise<void> {
  if (siteLoaded) {
    return
  }
  try {
    const site = await getPublicSite()
    siteTitle.value = site.site_title
    registrationEnabled.value = site.registration_enabled
    siteLoaded = true
  } catch {
    // 保持本地默认标题
  }
}
