import { ErrorBanner } from "@/components/common/ErrorBanner/ErrorBanner"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { useFrappeGetCall } from "frappe-react-sdk"
import { Bell, Bot, Check, ChevronRight, GitBranch, Github, Settings, ShieldCheck } from "lucide-react"

type Status = {
    github: boolean
    openai: boolean
    organizations: number
    projects: number
    branches: number
    policies: number
    notifications: number
    environments: number
    core_complete: boolean
}

const setupItems = (status: Status) => [
    { label: "Connect GitHub", description: "Configure OAuth or a GitHub App for private repositories and checks.", complete: status.github, href: "/app/github-settings", icon: Github, required: true },
    { label: "Create your structure", description: `${status.organizations} organizations, ${status.projects} projects, ${status.branches} branches`, complete: Boolean(status.organizations && status.projects && status.branches), href: "/app/commit-organization", icon: GitBranch, required: true },
    { label: "Review scan policies", description: `${status.policies} custom policies configured`, complete: status.policies > 0, href: "/app/commit-policy", icon: ShieldCheck, required: false },
    { label: "Add notifications", description: `${status.notifications} notification endpoints configured`, complete: status.notifications > 0, href: "/app/commit-notification-endpoint", icon: Bell, required: false },
    { label: "Add API environments", description: `${status.environments} test environments configured`, complete: status.environments > 0, href: "/app/commit-api-environment", icon: Settings, required: false },
    { label: "Enable AI documentation", description: "Optional OpenAI configuration for generated documentation.", complete: status.openai, href: "/app/open-ai-settings", icon: Bot, required: false },
]

export function ConfigurationOnboarding() {
    const { data, error, isLoading } = useFrappeGetCall<{ message: Status }>(
        "commit.api.onboarding.get_status",
        {},
        "commit-onboarding-status",
        { revalidateOnFocus: false }
    )

    if (error) return <ErrorBanner error={error} />
    if (isLoading || !data?.message) return null

    const status = data.message
    const items = setupItems(status)
    const completed = items.filter(item => item.complete).length

    return (
        <Card className="border-emerald-200 bg-gradient-to-br from-emerald-50/80 to-white">
            <CardHeader className="gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                    <div className="mb-2 flex items-center gap-2">
                        <CardTitle>Set up Commit</CardTitle>
                        <Badge variant={status.core_complete ? "secondary" : "default"}>{completed}/{items.length} complete</Badge>
                    </div>
                    <CardDescription>Connect your repository workflow and choose how Commit scans, tests, and alerts your team.</CardDescription>
                </div>
                <Button asChild variant="outline" size="sm"><a href="/app/commit">Open Desk workspace</a></Button>
            </CardHeader>
            <CardContent className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {items.map(item => {
                    const Icon = item.icon
                    return (
                        <a key={item.label} href={item.href} className="group flex items-start gap-3 rounded-lg border bg-white p-3 transition hover:border-emerald-400 hover:shadow-sm">
                            <span className={`mt-0.5 rounded-md p-2 ${item.complete ? "bg-emerald-100 text-emerald-700" : "bg-muted text-muted-foreground"}`}>
                                {item.complete ? <Check className="h-4 w-4" /> : <Icon className="h-4 w-4" />}
                            </span>
                            <span className="min-w-0 flex-1">
                                <span className="flex items-center gap-2 text-sm font-medium">{item.label}{item.required && !item.complete && <Badge variant="outline">Required</Badge>}</span>
                                <span className="mt-1 block text-xs text-muted-foreground">{item.description}</span>
                            </span>
                            <ChevronRight className="mt-2 h-4 w-4 text-muted-foreground transition group-hover:translate-x-0.5" />
                        </a>
                    )
                })}
            </CardContent>
        </Card>
    )
}
