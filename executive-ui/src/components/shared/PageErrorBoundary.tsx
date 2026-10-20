import { Component, type ReactNode, type ErrorInfo } from 'react'
import { AlertTriangle, RefreshCw, Upload } from 'lucide-react'

interface Props {
  children: ReactNode
  onReturnToUpload?: () => void
  pageName?: string
}

interface State {
  hasError: boolean
  errorMessage: string
}

export class PageErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, errorMessage: '' }
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      errorMessage: error?.message ?? 'An unexpected error occurred.',
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('[PageErrorBoundary] Caught error in', this.props.pageName ?? 'page', error, info.componentStack)
  }

  private handleRefresh = () => {
    this.setState({ hasError: false, errorMessage: '' })
  }

  render() {
    if (!this.state.hasError) return this.props.children

    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] p-8 text-center">
        <div className="card max-w-md w-full p-8 flex flex-col items-center gap-5">
          <div className="w-14 h-14 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-red-500" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-1">
              Something went wrong while rendering this section
            </h2>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {this.props.pageName
                ? `The ${this.props.pageName} page encountered an unexpected error.`
                : 'This page encountered an unexpected error.'}
            </p>
          </div>
          <div className="flex flex-col sm:flex-row gap-3 w-full">
            <button
              onClick={this.handleRefresh}
              className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium transition-colors"
            >
              <RefreshCw className="w-4 h-4" />
              Refresh section
            </button>
            {this.props.onReturnToUpload && (
              <button
                onClick={this.props.onReturnToUpload}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 text-sm font-medium transition-colors"
              >
                <Upload className="w-4 h-4" />
                Return to Overview
              </button>
            )}
          </div>
          <p className="text-xs text-gray-400 dark:text-gray-500">
            If this issue persists, try uploading your dataset again in the affected module, or refreshing the page.
          </p>
        </div>
      </div>
    )
  }
}
