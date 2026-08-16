import { FrappeProvider } from 'frappe-react-sdk'
import { lazy, Suspense } from 'react'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import PageNotFound from './components/common/PageNotFound/PageNotFound'

const DocsLandingPage = lazy(() => import('./pages/features/LandingPage/DocsLandingPage'))
const DocsPage = lazy(() => import('./pages/features/docs/DocsPage'))
const PageContent = lazy(() => import('./pages/features/docs/PageContent'))
const ViewDocs = lazy(() => import('./pages/features/docs/ViewDocs'))


function App() {

	const getSiteName = () => {
		// @ts-ignore
		if (window.frappe?.boot?.versions?.frappe && (window.frappe.boot.versions.frappe.startsWith('15') || window.frappe.boot.versions.frappe.startsWith('16'))) {
			// @ts-ignore
			return window.frappe?.boot?.sitename ?? import.meta.env.VITE_SITE_NAME
		}
		return import.meta.env.VITE_SITE_NAME

	}

	return (
		<FrappeProvider socketPort={import.meta.env.VITE_SOCKET_PORT ?? undefined} siteName={getSiteName()}>
			<BrowserRouter basename={import.meta.env.VITE_BASE_PATH}>
				<Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading…</div>}>
				<Routes>
					<Route index element={<DocsLandingPage />} />
					<Route path='/:ID' element={<ViewDocs />} >
						<Route index element={<DocsPage />} />
						<Route path=':pageID' element={<PageContent />} />
					</Route>
					<Route path='*' element={<PageNotFound />} />
				</Routes>
				</Suspense>
			</BrowserRouter>
		</FrappeProvider>
	)
}

export default App
