import { Header } from '@/components/common/Header'
import { ErrorBanner } from '@/components/common/ErrorBanner/ErrorBanner'
import { FullPageLoader } from '@/components/common/FullPageLoader/FullPageLoader'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Progress } from '@/components/ui/progress'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from '@/components/ui/use-toast'
import { FrappeConfig, FrappeContext, useFrappeGetCall, useFrappePostCall } from 'frappe-react-sdk'
import { AlertTriangle, ArrowRight, BookOpen, Box, Braces, CheckCircle2, GitBranch, GitCompare, Loader2, Network, Play, RefreshCcw, Search, ShieldAlert } from 'lucide-react'
import { useContext, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

type Snapshot = {
  name: string
  commit_hash: string
  risk_score: number
  change_count: number
  breaking_change_count: number
  finding_count: number
  component_count: number
  creation: string
}

type OverviewResponse = {
  project: string
  project_details?: { display_name?: string; repo_name?: string; org?: string; description?: string }
  branch: string
  branch_details?: { branch_name?: string; commit_hash?: string; last_fetched?: string; scan_status?: string; frequency?: string }
  snapshot?: Snapshot
  snapshots: Snapshot[]
  component_counts: { component_type: string; count: number }[]
  finding_counts: { severity: string; count: number }[]
}

type Change = {
  name: string
  component_type: string
  identity: string
  change_type: string
  severity: string
  breaking: number
  summary: string
}

type Finding = {
  name: string
  title: string
  severity: string
  status: string
  blocking?: number
  component_identity: string
  file_path?: string
  line_number?: number
  remediation?: string
}

type Architecture = {
  nodes: { id: string; type: string; label: string; file?: string }[]
  edges: { source: string; target: string; type: string; label?: string }[]
}

type Collection = {
  name: string
  collection_name: string
  description?: string
  environment?: string
  schedule?: string
  last_run?: { name: string; status: string; passed: number; failed: number; duration_ms: number }[]
}

type Analytics = {
  searches: { event_type: string; query: string; creation: string }[]
  audit_events: { action: string; user: string; project_branch?: string; creation: string }[]
}

const tone = (severity: string) => severity === 'Critical' || severity === 'High' ? 'destructive' : severity === 'Medium' ? 'default' : 'secondary'

const Metric = ({ label, value, detail, icon }: { label: string; value: string | number; detail: string; icon: React.ReactNode }) => (
  <Card className="rounded-xl shadow-sm">
    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
      <CardTitle className="text-sm font-medium">{label}</CardTitle>{icon}
    </CardHeader>
    <CardContent><div className="text-3xl font-semibold">{value}</div><p className="text-xs text-muted-foreground mt-1">{detail}</p></CardContent>
  </Card>
)

const Empty = ({ children }: { children: React.ReactNode }) => <div className="rounded-xl border border-dashed bg-muted/10 p-10 text-center text-sm text-muted-foreground">{children}</div>

export default function Intelligence() {
  const { ID = '' } = useParams()
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<{ entry_type: string; title: string; route: string }[]>([])
  const [docsName, setDocsName] = useState('')
  const [releaseNotes, setReleaseNotes] = useState('')
  const { call } = useContext(FrappeContext) as FrappeConfig
  const overviewCall = useFrappeGetCall<{ message: OverviewResponse }>('commit.api.intelligence.get_overview', { project_branch: ID })
  const changesCall = useFrappeGetCall<{ message: Change[] }>('commit.api.intelligence.get_changes', { project_branch: ID })
  const findingsCall = useFrappeGetCall<{ message: Finding[] }>('commit.api.intelligence.get_findings', { project_branch: ID })
  const architectureCall = useFrappeGetCall<{ message: Architecture }>('commit.api.intelligence.get_architecture', { project_branch: ID })
  const collectionsCall = useFrappeGetCall<{ message: Collection[] }>('commit.api.api_tests.get_branch_collections', { project_branch: ID })
  const analyticsCall = useFrappeGetCall<{ message: Analytics }>('commit.api.intelligence.get_analytics', { project_branch: ID })
  const updateFinding = useFrappePostCall('commit.api.intelligence.update_finding')
  const runCollection = useFrappePostCall('commit.api.api_tests.run_collection')
  const refreshBranch = useFrappePostCall('commit.commit.doctype.commit_project_branch.commit_project_branch.fetch_repo')

  const overview = overviewCall.data?.message
  const snapshot = overview?.snapshot
  const secondaryError = changesCall.error || findingsCall.error || architectureCall.error || collectionsCall.error || analyticsCall.error
  const components = useMemo(() => overview?.component_counts.reduce((sum, item) => sum + Number(item.count), 0) ?? 0, [overview])
  const scanInProgress = overview?.branch_details?.scan_status === 'Queued' || overview?.branch_details?.scan_status === 'Running'

  const refresh = async () => {
    try {
      await refreshBranch.call({ doc: {}, name: ID })
      toast({ description: 'Repository refresh and intelligence scan queued.' })
      await overviewCall.mutate()
    } catch {
      toast({ variant: 'destructive', description: 'Commit could not queue the repository scan.' })
    }
  }

  const changeFinding = async (finding: Finding, status: string) => {
    await updateFinding.call({ name: finding.name, status })
    await findingsCall.mutate()
    toast({ description: `Finding marked ${status.toLowerCase()}.` })
  }

  const suppressFinding = async (finding: Finding) => {
    const reason = window.prompt('Why should this finding be suppressed?')?.trim()
    if (!reason) return
    const expiry = new Date()
    expiry.setDate(expiry.getDate() + 30)
    await updateFinding.call({ name: finding.name, status: 'Suppressed', suppression_reason: reason, suppression_expires_on: expiry.toISOString().slice(0, 10) })
    await findingsCall.mutate()
    toast({ description: 'Finding suppressed for 30 days.' })
  }

  const execute = async (collection: Collection) => {
    const result = await runCollection.call({ collection: collection.name })
    await collectionsCall.mutate()
    toast({ description: `Collection finished: ${result.message.status}` })
  }

  const searchWorkspace = async () => {
    if (!query.trim()) return
    const result = await call.post('commit.api.intelligence.search', { query, project_branch: ID })
    setSearchResults(result.message ?? [])
  }

  const docsAction = async (action: 'import' | 'export' | 'pr') => {
    if (!docsName.trim()) {
      toast({ variant: 'destructive', description: 'Enter a Commit Docs name first.' })
      return
    }
    const method = action === 'import' ? 'commit.api.docs_sync.import_docs' : action === 'export' ? 'commit.api.docs_sync.export_docs' : 'commit.api.github_webhook.publish_docs_pr'
    const result = await call.post(method, { project_branch: ID, commit_docs: docsName })
    toast({ description: action === 'pr' ? `Pull request created: ${result.message.html_url}` : `Documentation ${action} completed.` })
  }

  const loadReleaseNotes = async () => {
    if (!snapshot) return
    const result = await call.get('commit.api.docs_sync.get_release_notes', { snapshot: snapshot.name })
    setReleaseNotes(result.message)
  }

  if (overviewCall.isLoading) return <FullPageLoader />

  return (
    <div className="min-h-screen bg-muted/20">
      <Header text="Commit Intelligence" />
      <main className="mx-auto max-w-7xl p-4 md:p-6 lg:p-8">
        <div className="mb-5 overflow-hidden rounded-2xl border bg-background shadow-sm">
          <div className="flex flex-col gap-5 p-5 md:flex-row md:items-center md:justify-between md:p-6">
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-muted-foreground"><span>{overview?.project_details?.org || 'Project'}</span><span>/</span><span>{overview?.project_details?.repo_name || overview?.project}</span><span>/</span><span className="flex items-center gap-1"><GitBranch className="h-3.5 w-3.5" />{overview?.branch_details?.branch_name || ID}</span></div>
              <h1 className="truncate text-2xl font-semibold tracking-tight">{overview?.project_details?.display_name || overview?.project || ID}</h1>
              <p className="mt-1 text-sm text-muted-foreground">Continuous repository intelligence, architecture, documentation, and verification.</p>
              <div className="mt-3 flex flex-wrap items-center gap-2"><Badge variant={overview?.branch_details?.scan_status === 'Failed' ? 'destructive' : 'secondary'}>{overview?.branch_details?.scan_status || 'Not scanned'}</Badge>{overview?.branch_details?.commit_hash && <code className="rounded bg-muted px-2 py-1 text-[11px]">{overview.branch_details.commit_hash.slice(0, 12)}</code>}{overview?.branch_details?.frequency && <Badge variant="outline">{overview.branch_details.frequency}</Badge>}</div>
            </div>
            <div className="flex flex-wrap gap-2"><Button onClick={refresh} disabled={refreshBranch.loading || scanInProgress}>{refreshBranch.loading || scanInProgress ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <RefreshCcw className="mr-2 h-4 w-4" />}{snapshot ? 'Refresh & scan' : 'Run first scan'}</Button><Button asChild variant="outline"><Link to={`/project-viewer/${ID}`}><Braces className="mr-2 h-4 w-4" />API Explorer</Link></Button><Button asChild variant="ghost"><Link to="/"><ArrowRight className="mr-2 h-4 w-4 rotate-180" />Projects</Link></Button></div>
          </div>
        </div>
        {overviewCall.error && <ErrorBanner error={overviewCall.error} />}
        {!overviewCall.error && secondaryError && <ErrorBanner error={secondaryError} />}

        <Tabs defaultValue="overview" className="space-y-4">
          <TabsList className="h-auto max-w-full flex-wrap justify-start rounded-xl border bg-background p-1 shadow-sm">
            <TabsTrigger value="overview">Overview</TabsTrigger><TabsTrigger value="changes">Changes</TabsTrigger><TabsTrigger value="findings">Findings</TabsTrigger><TabsTrigger value="architecture">Architecture</TabsTrigger><TabsTrigger value="tests">API Tests</TabsTrigger><TabsTrigger value="docs">Docs as Code</TabsTrigger><TabsTrigger value="search">Search</TabsTrigger><TabsTrigger value="activity">Activity</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-4">
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <Metric label="Risk score" value={snapshot?.risk_score ?? 0} detail="0 is clean; 100 requires immediate review" icon={<ShieldAlert className="h-4 w-4 text-muted-foreground" />} />
              <Metric label="Components" value={snapshot?.component_count ?? components} detail="APIs, DocTypes, hooks, dependencies and consumers" icon={<Box className="h-4 w-4 text-muted-foreground" />} />
              <Metric label="Breaking changes" value={snapshot?.breaking_change_count ?? 0} detail={`${snapshot?.change_count ?? 0} total changes in the latest scan`} icon={<GitCompare className="h-4 w-4 text-muted-foreground" />} />
              <Metric label="Open findings" value={snapshot?.finding_count ?? 0} detail="Frappe-specific security and quality findings" icon={<AlertTriangle className="h-4 w-4 text-muted-foreground" />} />
            </div>
            {!snapshot && <Card className="rounded-xl border-blue-200 bg-blue-50/50"><CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center"><div className="rounded-lg bg-blue-100 p-2 text-blue-700"><Play className="h-5 w-5" /></div><div className="flex-1"><div className="font-semibold text-blue-950">Establish the first intelligence baseline</div><p className="mt-1 text-sm text-blue-900/70">Commit will scan APIs, DocTypes, hooks, dependencies, consumers, policy findings, and architecture relationships.</p></div><Button onClick={refresh} disabled={refreshBranch.loading || scanInProgress}>Run first scan</Button></CardContent></Card>}
            <Card className="rounded-xl shadow-sm"><CardHeader><CardTitle>Risk posture</CardTitle><CardDescription>Latest commit {snapshot?.commit_hash?.slice(0, 12) || 'has not been scanned yet'}</CardDescription></CardHeader><CardContent><Progress value={snapshot?.risk_score ?? 0} /><div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">{overview?.component_counts?.map(item => <div key={item.component_type} className="rounded-lg border bg-muted/10 p-3"><div className="text-xl font-semibold">{item.count}</div><div className="text-xs text-muted-foreground">{item.component_type}</div></div>)}</div></CardContent></Card>
            <Card><CardHeader><CardTitle>Scan history</CardTitle></CardHeader><CardContent className="space-y-2">{overview?.snapshots.length ? overview.snapshots.map(item => <div key={item.name} className="flex items-center justify-between rounded-md border p-3"><div><code className="text-xs">{item.commit_hash?.slice(0, 12)}</code><div className="text-xs text-muted-foreground">{new Date(item.creation).toLocaleString()}</div></div><div className="flex gap-2"><Badge variant={item.breaking_change_count ? 'destructive' : 'secondary'}>{item.breaking_change_count || 0} breaking</Badge><Badge variant="outline">Risk {item.risk_score || 0}</Badge></div></div>) : <Empty>Run the branch scan to establish the first intelligence baseline.</Empty>}</CardContent></Card>
          </TabsContent>

          <TabsContent value="changes"><Card><CardHeader><CardTitle>Component changes</CardTitle><CardDescription>Stable-identity comparison against the previous successful scan.</CardDescription></CardHeader><CardContent className="space-y-2">{changesCall.data?.message.length ? changesCall.data.message.map(change => <div key={change.name} className="rounded-md border p-3"><div className="flex flex-wrap items-center gap-2"><Badge variant={change.breaking ? 'destructive' : 'outline'}>{change.change_type}</Badge><Badge variant={tone(change.severity)}>{change.severity}</Badge><span className="text-xs text-muted-foreground">{change.component_type}</span><code className="text-sm font-medium">{change.identity}</code></div><p className="mt-2 text-sm text-muted-foreground">{change.summary}</p></div>) : <Empty>No component changes were detected.</Empty>}</CardContent></Card></TabsContent>

          <TabsContent value="findings"><Card><CardHeader><CardTitle>Policy findings</CardTitle><CardDescription>Assign, acknowledge, resolve, or suppress findings with an auditable reason.</CardDescription></CardHeader><CardContent className="space-y-3">{findingsCall.data?.message.length ? findingsCall.data.message.map(finding => <div key={finding.name} className="rounded-md border p-4"><div className="flex flex-wrap items-center gap-2"><Badge variant={tone(finding.severity)}>{finding.severity}</Badge>{finding.blocking ? <Badge variant="destructive">Blocking</Badge> : null}<Badge variant="outline">{finding.status}</Badge><span className="font-medium">{finding.title}</span></div><code className="mt-2 block text-xs text-muted-foreground">{finding.file_path}{finding.line_number ? `:${finding.line_number}` : ''} · {finding.component_identity}</code><p className="mt-2 text-sm">{finding.remediation}</p><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="outline" onClick={() => changeFinding(finding, 'Acknowledged')}>Acknowledge</Button><Button size="sm" onClick={() => changeFinding(finding, 'Resolved')}><CheckCircle2 className="mr-2 h-4 w-4" />Resolve</Button><Button size="sm" variant="ghost" onClick={() => suppressFinding(finding)}>Suppress 30 days</Button></div></div>) : <Empty>No findings for this branch.</Empty>}</CardContent></Card></TabsContent>

          <TabsContent value="architecture"><Card><CardHeader><CardTitle>Architecture inventory</CardTitle><CardDescription>Relationships between DocTypes, APIs, frontend consumers, hooks, and dependencies.</CardDescription></CardHeader><CardContent>{architectureCall.isLoading ? <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin text-muted-foreground" /></div> : architectureCall.data?.message?.nodes?.length ? <div className="grid gap-4 lg:grid-cols-3"><div className="space-y-2 lg:col-span-2">{architectureCall.data.message.nodes.slice(0, 150).map(node => <div key={node.id} className="flex items-center gap-2 rounded-md border p-2"><Network className="h-4 w-4 text-muted-foreground" /><Badge variant="outline">{node.type}</Badge><span className="truncate text-sm">{node.label}</span><code className="ml-auto hidden text-xs text-muted-foreground md:block">{node.file}</code></div>)}</div><div><h3 className="mb-2 font-medium">Relationships</h3><div className="space-y-2">{architectureCall.data.message.edges?.slice(0, 100).map((edge, index) => <div key={`${edge.source}-${edge.target}-${index}`} className="rounded-md bg-muted p-2 text-xs"><div className="truncate">{edge.source}</div><div className="my-1 text-muted-foreground">↓ {edge.type} {edge.label}</div><div className="truncate">{edge.target}</div></div>)}</div></div></div> : <Empty>Run a scan to build the architecture inventory.</Empty>}</CardContent></Card></TabsContent>

          <TabsContent value="tests"><Card><CardHeader><CardTitle>API collections</CardTitle><CardDescription>Encrypted environments, assertions, scheduled smoke tests, and execution history.</CardDescription></CardHeader><CardContent className="space-y-3">{collectionsCall.data?.message.length ? collectionsCall.data.message.map(collection => { const last = collection.last_run?.[0]; return <div key={collection.name} className="flex flex-col gap-3 rounded-md border p-4 md:flex-row md:items-center"><div><div className="font-medium">{collection.collection_name}</div><p className="text-sm text-muted-foreground">{collection.description || 'No description'} · {collection.environment || 'No environment'} · {collection.schedule || 'Manual'}</p>{last && <p className="text-xs text-muted-foreground">Last run: {last.status} · {last.passed || 0} passed · {last.failed || 0} failed · {last.duration_ms || 0}ms</p>}</div><Button className="md:ml-auto" size="sm" disabled={runCollection.loading} onClick={() => execute(collection)}><Play className="mr-2 h-4 w-4" />Run</Button></div> }) : <Empty>Create a Commit API Collection and environment in Desk to start repeatable API verification.</Empty>}</CardContent></Card></TabsContent>

          <TabsContent value="docs" className="space-y-4"><Card><CardHeader><CardTitle>Docs-as-code workflow</CardTitle><CardDescription>Import repository Markdown, export reviewed pages, or open a GitHub pull request.</CardDescription></CardHeader><CardContent><div className="flex flex-col gap-2 md:flex-row"><Input value={docsName} onChange={event => setDocsName(event.target.value)} placeholder="Commit Docs name" /><Button variant="outline" onClick={() => docsAction('import')}><BookOpen className="mr-2 h-4 w-4" />Import Markdown</Button><Button variant="outline" onClick={() => docsAction('export')}>Export branch</Button><Button onClick={() => docsAction('pr')}>Open PR</Button></div></CardContent></Card><Card><CardHeader><CardTitle>Release notes</CardTitle><CardDescription>Generated deterministically from classified snapshot changes.</CardDescription></CardHeader><CardContent><Button variant="outline" onClick={loadReleaseNotes}>Generate release notes</Button>{releaseNotes && <pre className="mt-3 max-h-96 overflow-auto whitespace-pre-wrap rounded-md bg-muted p-4 text-sm">{releaseNotes}</pre>}</CardContent></Card></TabsContent>

          <TabsContent value="search"><Card><CardHeader><CardTitle>Unified search</CardTitle><CardDescription>Search documentation, APIs, DocTypes, hooks, dependencies, and findings.</CardDescription></CardHeader><CardContent><div className="flex gap-2"><Input value={query} onChange={event => setQuery(event.target.value)} onKeyDown={event => event.key === 'Enter' && searchWorkspace()} placeholder="Search this branch…" /><Button onClick={searchWorkspace}><Search className="mr-2 h-4 w-4" />Search</Button></div><div className="mt-4 space-y-2">{searchResults.map((result, index) => <Link key={`${result.route}-${index}`} to={result.route || '#'} className="block rounded-md border p-3 hover:bg-muted"><Badge variant="outline">{result.entry_type}</Badge><span className="ml-2 text-sm font-medium">{result.title}</span></Link>)}</div></CardContent></Card></TabsContent>

          <TabsContent value="activity"><div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Audit trail</CardTitle><CardDescription>Security-sensitive actions and automation delivery.</CardDescription></CardHeader><CardContent className="space-y-2">{analyticsCall.data?.message?.audit_events?.length ? analyticsCall.data.message.audit_events.map((event, index) => <div key={`${event.action}-${index}`} className="rounded-md border p-3"><div className="text-sm font-medium">{event.action}</div><div className="text-xs text-muted-foreground">{event.user} · {new Date(event.creation).toLocaleString()}</div></div>) : <Empty>No audit events yet.</Empty>}</CardContent></Card><Card><CardHeader><CardTitle>Search demand</CardTitle><CardDescription>Recent searches and content gaps.</CardDescription></CardHeader><CardContent className="space-y-2">{analyticsCall.data?.message?.searches?.length ? analyticsCall.data.message.searches.map((event, index) => <div key={`${event.query}-${index}`} className="flex items-center justify-between rounded-md border p-3"><span className="text-sm">{event.query}</span><Badge variant={event.event_type === 'Search Miss' ? 'destructive' : 'secondary'}>{event.event_type}</Badge></div>) : <Empty>No search activity yet.</Empty>}</CardContent></Card></div></TabsContent>
        </Tabs>
      </main>
    </div>
  )
}
