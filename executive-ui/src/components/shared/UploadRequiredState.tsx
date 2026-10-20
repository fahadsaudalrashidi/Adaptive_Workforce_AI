import { Upload } from 'lucide-react'
import { useLanguage } from '../../context/LanguageContext'

interface UploadRequiredStateProps {
  onNavigate?: () => void
}

export function UploadRequiredState({ onNavigate }: UploadRequiredStateProps) {
  const { t } = useLanguage()

  return (
    <div className="flex flex-col items-center justify-center py-24 text-center">
      <div className="w-16 h-16 rounded-2xl bg-blue-50 dark:bg-blue-950/30 flex items-center justify-center mb-5">
        <Upload size={28} className="text-blue-500" />
      </div>
      <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-200 mb-2">
        {t('No Organization Data Loaded', 'لم يتم تحميل بيانات المؤسسة')}
      </h2>
      <p className="text-sm text-slate-500 dark:text-slate-400 max-w-sm leading-relaxed">
        {t(
          'Load your organization data to activate workforce intelligence. All analysis is powered exclusively by your data — fully offline.',
          'حمّل بيانات مؤسستك لتفعيل ذكاء القوى العاملة. جميع التحليلات مدعومة ببياناتك حصراً — دون اتصال بالإنترنت.'
        )}
      </p>
      {onNavigate && (
        <button
          onClick={onNavigate}
          className="mt-6 btn-primary flex items-center gap-2"
        >
          <Upload size={14} />
          {t('Go to Data Intake', 'الذهاب إلى استيعاب البيانات')}
        </button>
      )}
    </div>
  )
}
