import { ErrorBanner, getErrorMessage } from "@/components/common/ErrorBanner/ErrorBanner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import { toast } from "@/components/ui/use-toast"
import { useDebounce } from "@/hooks/useDebounce"
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk"
import { Bell, Bot, Building2, Check, ChevronRight, ChevronsUpDown, ExternalLink, GitBranch, Github, Loader2, Lock, Settings, ShieldCheck, UserRound } from "lucide-react"
import { useEffect, useMemo, useState } from "react"

type Status = {
    github: boolean
    github_connected: boolean
    github_app_created: boolean
    github_account?: string
    github_account_type?: string
    github_repository_selection?: string
    github_webhooks_enabled: boolean
    openai: boolean
    organizations: number
    projects: number
    branches: number
    policies: number
    notifications: number
    environments: number
    core_complete: boolean
}

type Repository = {
    id: number
    name: string
    full_name: string
    owner: string
    avatar_url?: string
    private: boolean
    archived: boolean
    description?: string
    default_branch: string
    language?: string
    imported: boolean
}

type GitHubOrganization = {
    login: string
    avatar_url?: string
    html_url?: string
}

type ConnectionStart =
    | { kind: "redirect", url: string }
    | { kind: "manifest", action: string, state: string, manifest: Record<string, unknown> }

const setupItems = (status: Status) => [
    { label: "Create your structure", description: `${status.organizations} organizations, ${status.projects} projects, ${status.branches} branches`, complete: Boolean(status.organizations && status.projects && status.branches), href: "/app/commit-organization", icon: GitBranch, required: true },
    { label: "Review scan policies", description: `${status.policies} custom policies configured`, complete: status.policies > 0, href: "/app/commit-policy", icon: ShieldCheck, required: false },
    { label: "Add notifications", description: `${status.notifications} notification endpoints configured`, complete: status.notifications > 0, href: "/app/commit-notification-endpoint", icon: Bell, required: false },
    { label: "Add API environments", description: `${status.environments} test environments configured`, complete: status.environments > 0, href: "/app/commit-api-environment", icon: Settings, required: false },
    { label: "Enable AI documentation", description: "Optional OpenAI configuration for generated documentation.", complete: status.openai, href: "/app/open-ai-settings", icon: Bot, required: false },
]

function submitManifest(start: Extract<ConnectionStart, { kind: "manifest" }>) {
    const form = document.createElement("form")
    form.method = "POST"
    form.action = start.action
    for (const [name, value] of Object.entries({ manifest: JSON.stringify(start.manifest), state: start.state })) {
        const input = document.createElement("input")
        input.type = "hidden"
        input.name = name
        input.value = value
        form.appendChild(input)
    }
    document.body.appendChild(form)
    form.submit()
}

function RepositoryPicker({ open, onOpenChange, onImported }: { open: boolean, onOpenChange: (open: boolean) => void, onImported: () => void }) {
    const [selected, setSelected] = useState<Set<number>>(new Set())
    const { data, error, isLoading, mutate } = useFrappeGetCall<{ message: Repository[] }>(
        "commit.api.github_connection.list_repositories",
        {},
        open ? "commit-github-repositories" : null,
        { revalidateOnFocus: false }
    )
    const importer = useFrappePostCall<{ message: { created: number, repositories: unknown[] } }>("commit.api.github_connection.import_repositories")
    const repositories = data?.message ?? []
    const available = repositories.filter(repository => !repository.imported && !repository.archived)

    useEffect(() => {
        if (!open) setSelected(new Set())
    }, [open])

    const toggle = (id: number) => {
        setSelected(current => {
            const next = new Set(current)
            if (next.has(id)) next.delete(id)
            else next.add(id)
            return next
        })
    }

    const importSelected = async () => {
        try {
            const result = await importer.call({ repository_ids: JSON.stringify([...selected]) })
            toast({ description: `${result.message.created} repositories imported. Initial scans are now queued.` })
            setSelected(new Set())
            await mutate()
            onImported()
        } catch (callError) {
            toast({ variant: "destructive", description: getErrorMessage(callError as never) || "Could not import repositories." })
        }
    }

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-3xl">
                <DialogHeader>
                    <DialogTitle>Import GitHub repositories</DialogTitle>
                    <DialogDescription>Select repositories to create their Commit organization, project, and default branch automatically.</DialogDescription>
                </DialogHeader>
                {error && <ErrorBanner error={error} />}
                <div className="max-h-[52vh] space-y-2 overflow-y-auto pr-1">
                    {isLoading && <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading repositories…</div>}
                    {!isLoading && repositories.length === 0 && <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No repositories are available to this installation. Add repository access in GitHub and try again.</div>}
                    {repositories.map(repository => {
                        const disabled = repository.imported || repository.archived
                        return (
                            <label key={repository.id} className={`flex items-start gap-3 rounded-lg border p-3 transition-colors ${disabled ? "bg-muted/40 opacity-70" : "cursor-pointer hover:border-gray-300 hover:bg-gray-50/70"}`}>
                                <Checkbox checked={repository.imported || selected.has(repository.id)} disabled={disabled} onCheckedChange={() => toggle(repository.id)} className="mt-1" />
                                {repository.avatar_url && <img src={repository.avatar_url} alt="" className="h-8 w-8 rounded-md" />}
                                <span className="min-w-0 flex-1">
                                    <span className="flex flex-wrap items-center gap-2 text-sm font-medium">
                                        {repository.full_name}
                                        {repository.private && <Badge variant="outline"><Lock className="mr-1 h-3 w-3" />Private</Badge>}
                                        {repository.imported && <Badge variant="secondary">Imported</Badge>}
                                        {repository.archived && <Badge variant="outline">Archived</Badge>}
                                    </span>
                                    <span className="mt-1 block truncate text-xs text-muted-foreground">{repository.description || "No description"} · {repository.default_branch}{repository.language ? ` · ${repository.language}` : ""}</span>
                                </span>
                            </label>
                        )
                    })}
                </div>
                <DialogFooter className="items-center sm:justify-between">
                    <span className="text-xs text-muted-foreground">{available.length} available · {selected.size} selected</span>
                    <div className="flex gap-2">
                        <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
                        <Button onClick={importSelected} disabled={!selected.size || importer.loading}>
                            {importer.loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                            Import selected
                        </Button>
                    </div>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    )
}

export function ConfigurationOnboarding() {
    const [pickerOpen, setPickerOpen] = useState(false)
    const [ownerSelectorOpen, setOwnerSelectorOpen] = useState(false)
    const [organizationQuery, setOrganizationQuery] = useState("")
    const [githubOrganization, setGithubOrganization] = useState("")
    const debouncedOrganizationQuery = useDebounce(organizationQuery.trim(), 300)
    const { data, error, isLoading, mutate } = useFrappeGetCall<{ message: Status }>(
        "commit.api.onboarding.get_status",
        {},
        "commit-onboarding-status",
        { revalidateOnFocus: false }
    )
    const organizationSearch = useFrappeGetCall<{ message: GitHubOrganization[] }>(
        "commit.api.github_connection.search_organizations",
        { query: debouncedOrganizationQuery },
        debouncedOrganizationQuery.length >= 2 ? `commit-github-organizations-${debouncedOrganizationQuery}` : null,
        { revalidateOnFocus: false }
    )
    const connection = useFrappePostCall<{ message: ConnectionStart }>("commit.api.github_connection.start_connection")

    useEffect(() => {
        const params = new URLSearchParams(window.location.search)
        const github = params.get("github")
        if (!github) return
        if (github === "connected") {
            toast({ description: "GitHub connected. Choose the repositories Commit should scan." })
            setPickerOpen(true)
            void mutate()
        } else if (github === "error") {
            toast({ variant: "destructive", description: "GitHub authorization was not completed. You can safely try again." })
        } else if (github === "restart_required") {
            toast({ variant: "destructive", description: "The previous GitHub App setup was incomplete. Start the connection again to create a valid App." })
        }
        params.delete("github")
        params.delete("reason")
        const query = params.toString()
        window.history.replaceState({}, "", `${window.location.pathname}${query ? `?${query}` : ""}${window.location.hash}`)
    }, [mutate])

    const status = data?.message
    const items = useMemo(() => status ? setupItems(status) : [], [status])

    if (error) return <ErrorBanner error={error} />
    if (isLoading || !status) return null

    const completed = items.filter(item => item.complete).length + (status.github_connected ? 1 : 0)

    const connect = async () => {
        try {
            const result = (await connection.call({ organization: githubOrganization.trim() })).message
            if (result.kind === "manifest") submitManifest(result)
            else window.location.assign(result.url)
        } catch (callError) {
            toast({ variant: "destructive", description: getErrorMessage(callError as never) || "Could not start GitHub setup." })
        }
    }

    return (
        <>
            <Card className="rounded-lg border bg-white shadow-sm">
                <CardHeader className="gap-3 border-b px-6 py-5 md:flex-row md:items-start md:justify-between">
                    <div>
                        <div className="mb-1.5 flex items-center gap-2.5">
                            <CardTitle className="text-lg">Set up Commit</CardTitle>
                            <Badge variant="secondary" className="rounded-full font-medium">{completed}/{items.length + 1} complete</Badge>
                        </div>
                        <CardDescription>Connect your repository workflow and choose how Commit scans, tests, and alerts your team.</CardDescription>
                    </div>
                    <Button asChild variant="outline" size="sm" className="rounded-full px-4"><a href="/app/commit">Open Desk workspace</a></Button>
                </CardHeader>
                <CardContent className="grid gap-3 p-5 md:grid-cols-2 xl:grid-cols-3">
                    <div className="flex items-start gap-3 rounded-lg border bg-white p-4 shadow-sm">
                        <span className={`mt-0.5 rounded-md p-2 ${status.github_connected ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-500"}`}>
                            {status.github_connected ? <Check className="h-4 w-4" /> : <Github className="h-4 w-4" />}
                        </span>
                        <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-2 text-sm font-semibold">Connect GitHub{!status.github_connected && <Badge variant="secondary" className="font-medium">Required</Badge>}</span>
                            <span className="mt-1 block text-xs text-muted-foreground">
                                {status.github_connected ? `${status.github_account} connected · ${status.github_repository_selection || "repository"} access` : status.github_app_created ? "GitHub App created. Finish installation and authorization." : "Create, install, and authorize a private GitHub App automatically."}
                            </span>
                            {!status.github_webhooks_enabled && status.github_connected && <span className="mt-1 block text-xs text-amber-700">Webhooks need a public HTTPS site; manual scans still work locally.</span>}
                            {!status.github_connected && !status.github_app_created && (
                                <span className="mt-3 block">
                                    <span className="mb-1.5 block text-xs font-medium text-gray-600">GitHub App owner</span>
                                    <Popover open={ownerSelectorOpen} onOpenChange={setOwnerSelectorOpen}>
                                        <PopoverTrigger asChild>
                                            <Button variant="outline" role="combobox" aria-expanded={ownerSelectorOpen} className="h-9 w-full justify-between bg-white px-3 font-normal">
                                                <span className="flex min-w-0 items-center gap-2">
                                                    {githubOrganization ? <Building2 className="h-4 w-4 text-gray-500" /> : <UserRound className="h-4 w-4 text-gray-500" />}
                                                    <span className="truncate">{githubOrganization || "Personal account"}</span>
                                                </span>
                                                <ChevronsUpDown className="h-4 w-4 shrink-0 text-gray-400" />
                                            </Button>
                                        </PopoverTrigger>
                                        <PopoverContent align="start" className="w-[320px] p-0">
                                            <Command shouldFilter={false}>
                                                <CommandInput value={organizationQuery} onValueChange={setOrganizationQuery} placeholder="Search GitHub organizations…" />
                                                <CommandList>
                                                    <CommandGroup heading="App owner">
                                                        <CommandItem value="personal-account" onSelect={() => { setGithubOrganization(""); setOwnerSelectorOpen(false) }}>
                                                            <UserRound className="mr-2 h-4 w-4" />
                                                            <span className="flex-1">Personal account</span>
                                                            {!githubOrganization && <Check className="h-4 w-4" />}
                                                        </CommandItem>
                                                        {(organizationSearch.data?.message ?? []).map(organization => (
                                                            <CommandItem key={organization.login} value={organization.login} onSelect={() => { setGithubOrganization(organization.login); setOwnerSelectorOpen(false) }}>
                                                                {organization.avatar_url ? <img src={organization.avatar_url} alt="" className="mr-2 h-5 w-5 rounded" /> : <Building2 className="mr-2 h-4 w-4" />}
                                                                <span className="flex-1">{organization.login}</span>
                                                                {githubOrganization === organization.login && <Check className="h-4 w-4" />}
                                                            </CommandItem>
                                                        ))}
                                                    </CommandGroup>
                                                    {organizationSearch.isLoading && <div className="flex items-center justify-center gap-2 py-4 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Searching GitHub…</div>}
                                                    {debouncedOrganizationQuery.length >= 2 && !organizationSearch.isLoading && <CommandEmpty>No organizations found.</CommandEmpty>}
                                                </CommandList>
                                            </Command>
                                        </PopoverContent>
                                    </Popover>
                                    <span className="mt-1.5 block text-[11px] leading-4 text-muted-foreground">Choose the organization that should own this private App, or use your personal account.</span>
                                </span>
                            )}
                            <span className="mt-3 flex flex-wrap gap-2">
                                {status.github_connected ? (
                                    <Button size="sm" className="rounded-full px-4 shadow-sm" onClick={() => setPickerOpen(true)}>Manage repositories</Button>
                                ) : (
                                    <Button size="sm" className="rounded-full px-4 shadow-sm" onClick={connect} disabled={connection.loading}>
                                        {connection.loading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Github className="mr-2 h-4 w-4" />}
                                        {status.github_app_created ? "Finish GitHub setup" : "Connect GitHub"}
                                    </Button>
                                )}
                                <Button asChild size="sm" variant="ghost"><a href="/app/github-settings">Advanced <ExternalLink className="ml-1 h-3 w-3" /></a></Button>
                            </span>
                        </span>
                    </div>
                    {items.map(item => {
                        const Icon = item.icon
                        return (
                            <a key={item.label} href={item.href} className="group flex items-start gap-3 rounded-lg border bg-white p-4 shadow-sm transition-colors hover:border-gray-300 hover:bg-gray-50/70">
                                <span className={`mt-0.5 rounded-md p-2 ${item.complete ? "bg-green-50 text-green-600" : "bg-gray-100 text-gray-500"}`}>
                                    {item.complete ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                                </span>
                                <span className="min-w-0 flex-1">
                                    <span className="flex items-center gap-2 text-sm font-semibold">{item.label}{item.required && !item.complete && <Badge variant="secondary" className="font-medium">Required</Badge>}</span>
                                    <span className="mt-1 block text-xs text-muted-foreground">{item.description}</span>
                                </span>
                                <ChevronRight className="mt-2 h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5" />
                            </a>
                        )
                    })}
                </CardContent>
            </Card>
            {status.github_connected && <RepositoryPicker open={pickerOpen} onOpenChange={setPickerOpen} onImported={() => void mutate()} />}
        </>
    )
}
