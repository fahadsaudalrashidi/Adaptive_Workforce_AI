import { Sun, Moon, Languages, Menu, ShieldCheck, Bell } from 'lucide-react'
import { useTheme } from '../context/ThemeContext'
import { useLanguage } from '../context/LanguageContext'

interface TopBarProps {
  onToggleSidebar: () => void
  companyName: string
  companyNameAr: string
}

export function TopBar({ onToggleSidebar, companyName, companyNameAr }: TopBarProps) {
  const { theme, toggleTheme } = useTheme()
  const { lang, toggleLang, t, isAr } = useLanguage()

  return (
    <header className="h-14 flex items-center justify-between px-4 bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 flex-shrink-0">
      {/* Left: menu toggle + breadcrumb */}
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="btn-ghost p-2 rounded-lg"
          aria-label="Toggle sidebar"
        >
          <Menu size={18} />
        </button>

        <div className="hidden sm:flex items-center gap-2">
          <span className="text-slate-400 dark:text-slate-500 text-sm">
            {isAr ? companyNameAr : companyName}
          </span>
          <span className="text-slate-300 dark:text-slate-700">/</span>
          <span className="text-slate-700 dark:text-slate-300 text-sm font-medium">
            {t('Executive Intelligence', 'الذكاء التنفيذي')}
          </span>
        </div>
      </div>

      {/* Center: governance status pill */}
      <div className="hidden md:flex items-center gap-2 px-3 py-1.5 bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/50 rounded-full">
        <ShieldCheck size={14} className="text-emerald-500" />
        <span className="text-xs font-medium text-emerald-700 dark:text-emerald-400">
          {t('Governance Active', 'الحوكمة نشطة')}
        </span>
        <span className="text-xs text-emerald-500 dark:text-emerald-500/70">•</span>
        <span className="text-xs text-emerald-600 dark:text-emerald-500/70">
          {t('PDPL Compliant', 'متوافق مع لوائح البيانات')}
        </span>
      </div>

      {/* Right: controls */}
      <div className="flex items-center gap-2">
        {/* Language toggle */}
        <button
          onClick={toggleLang}
          className="btn-ghost flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium"
          title={t('Switch to Arabic', 'التبديل إلى الإنجليزية')}
        >
          <Languages size={15} />
          <span>{lang === 'en' ? 'عربي' : 'EN'}</span>
        </button>

        {/* Theme toggle */}
        <button
          onClick={toggleTheme}
          className="btn-ghost p-2 rounded-lg"
          aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
        >
          {theme === 'dark' ? <Sun size={17} /> : <Moon size={17} />}
        </button>

        {/* Notifications (placeholder) */}
        <button className="btn-ghost p-2 rounded-lg relative" aria-label="Notifications">
          <Bell size={17} />
          <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 bg-amber-400 rounded-full" />
        </button>

        {/* Tenant badge */}
        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
          <div className="w-2 h-2 bg-emerald-400 rounded-full animate-pulse-slow" />
          <span className="text-xs text-slate-600 dark:text-slate-400 font-medium">
            {t('AWI Platform', 'منصة AWI')}
          </span>
        </div>
      </div>
    </header>
  )
}
