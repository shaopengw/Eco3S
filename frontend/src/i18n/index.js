import { reactive } from 'vue'
import zh from './zh-CN'
import en from './en-US'

const i18n = reactive({
  locale: 'en-US',
  messages: {
    'zh-CN': zh,
    'en-US': en
  }
})

export function useI18n() {
  const t = (key) => {
    const keys = key.split('.')
    let value = i18n.messages[i18n.locale]
    
    for (const k of keys) {
      if (value && typeof value === 'object') {
        value = value[k]
      } else {
        return key
      }
    }
    
    return value || key
  }

  const setLocale = (locale) => {
    i18n.locale = locale
  }

  const getLocale = () => {
    return i18n.locale
  }

  return {
    t,
    setLocale,
    getLocale,
    locale: i18n.locale
  }
}

export default i18n
