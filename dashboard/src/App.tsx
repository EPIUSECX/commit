import { lazy, Suspense } from 'react'
import { FrappeProvider } from 'frappe-react-sdk'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import PageNotFound from './components/common/PageNotFound/PageNotFound'
import Overview from './pages/overview/Overview'

const APIViewerContainer = lazy(() => import('./pages/features/api_viewer/APIViewer'))
const AppAPIViewerContainer = lazy(() => import('./pages/features/api_viewer/AppAPIViewer'))
const ViewDocs = lazy(() => import('./pages/features/docs/ViewDocs'))
const ERDViewer = lazy(() => import('./pages/features/erd/ERDViewer'))
const CreateERD = lazy(() => import('./pages/features/erd/meta/CreateERDForMeta'))
const DocsMainPage = lazy(() => import('./components/features/documentation/DocsMainPage').then(module => ({ default: module.DocsMainPage })))
const PageTable = lazy(() => import('./pages/features/docs/DocsEditor/PageTable').then(module => ({ default: module.PageTable })))
const Sidebar = lazy(() => import('./pages/features/docs/Sidebar/DashboardSidebar').then(module => ({ default: module.Sidebar })))
const DocsSettings = lazy(() => import('./pages/features/docs/Settings/DocsSettings').then(module => ({ default: module.DocsSettings })))
const DashboardNavbar = lazy(() => import('./pages/features/docs/Navbar/DashboardNavbar').then(module => ({ default: module.DashboardNavbar })))
const DashboardFooter = lazy(() => import('./pages/features/docs/Footer/DashboardFooter').then(module => ({ default: module.DashboardFooter })))
const Intelligence = lazy(() => import('./pages/features/intelligence/Intelligence'))


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
        {/* <UserProvider> */}
        <Suspense fallback={<div className="flex min-h-screen items-center justify-center">Loading…</div>}>
        <Routes>
          {/** Public Routes */}
          {/* <Route path="/sign-up" element={<SignUp />} /> */}

          {/** Private Routes */}
          {/* <Route path="/" element={<ProtectedRoute />} /> */}
          {/* default route on '/' */}
          <Route path="/" index element={<Overview />} />
          {/*TODO: Need to Change below route */}
          <Route path='/project-erd' element={<ERDViewer />} />
          <Route path="/project-viewer/:ID" element={<APIViewerContainer />} />
          <Route path="/meta-viewer/:ID" element={<AppAPIViewerContainer />} />
          <Route path='/meta-erd/:ID' element={<ERDViewer />} />
          <Route path='/meta-erd/create' element={<CreateERD />} />
          <Route path='/intelligence/:ID' element={<Intelligence />} />
          <Route path='/docs' element={<Navigate to={'/'} />} />
          <Route path='/docs/:ID' element={<ViewDocs />} >
            <Route index element={<Navigate to={'overview'} />} />
            <Route path='overview' element={<DocsMainPage />} />
            <Route path='editor' element={<PageTable />}>
              {/* Add nested dynamic route inside editor */}
              <Route path=':pageID' element={<PageTable />} />
            </Route>
            <Route path='sidebar' element={<Sidebar />} />
            <Route path='navbar' element={<DashboardNavbar />} />
            <Route path='footer' element={<DashboardFooter />} />
            <Route path='settings' element={<DocsSettings />} />
          </Route>
          <Route path='*' element={<PageNotFound />} />
        </Routes>
        </Suspense>
        {/* </UserProvider> */}
      </BrowserRouter>
    </FrappeProvider>
  )
}

export default App
