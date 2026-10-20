import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import type { Language } from '../types'

interface LanguageContextValue {
  lang: Language
  toggleLang: () => void
  isAr: boolean
  t: (en: string, ar: string) => string
}

const LanguageContext = createContext<LanguageContextValue | null>(null)

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Language>(() => {
    return (localStorage.getItem('awi-lang') as Language) ?? 'en'
  })

  useEffect(() => {
    const root = document.documentElement
    root.setAttribute('lang', lang)
    root.setAttribute('dir', lang === 'ar' ? 'rtl' : 'ltr')
    root.style.fontFamily = lang === 'ar' ? "'Cairo', system-ui, sans-serif" : "'Inter', system-ui, sans-serif"
    localStorage.setItem('awi-lang', lang)
  }, [lang])

  const toggleLang = () => setLang(l => (l === 'en' ? 'ar' : 'en'))
  const t = (en: string, ar: string) => (lang === 'ar' ? ar : en)

  return (
    <LanguageContext.Provider value={{ lang, toggleLang, isAr: lang === 'ar', t }}>
      {children}
    </LanguageContext.Provider>
  )
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext)
  if (!ctx) throw new Error('useLanguage must be used within LanguageProvider')
  return ctx
}
