import { ErrorBanner, getErrorMessage } from "@/components/common/ErrorBanner/ErrorBanner"
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { toast } from "@/components/ui/use-toast"
import { useFrappeGetCall, useFrappePostCall } from "frappe-react-sdk"
import { Building2, ExternalLink, Github, Loader2, Plus, RefreshCcw, ShieldCheck, Trash2, UserRound } from "lucide-react"
import { useState } from "react"

export type GitHubInstallation = {
    id: string
    account?: string
    account_type?: string
    repository_selection?: string
    project_count?: number
}

type InstallationResponse = {
    app_name?: string
    app_url?: string
    app_created: boolean
    installations: GitHubInstallation[]
}

export function GitHubConnectionManager({
    open,
    onOpenChange,
    onAddAccount,
    onManageRepositories,
    onChanged,
}: {
    open: boolean
    onOpenChange: (open: boolean) => void
    onAddAccount: () => void
    onManageRepositories: () => void
    onChanged: () => void
}) {
    const [disconnecting, setDisconnecting] = useState<GitHubInstallation | null>(null)
    const [resetOpen, setResetOpen] = useState(false)
    const installationsCall = useFrappeGetCall<{ message: InstallationResponse }>(
        "commit.api.github_connection.list_installations",
        {},
        open ? "commit-github-installations" : null,
        { revalidateOnFocus: false }
    )
    const disconnect = useFrappePostCall("commit.api.github_connection.disconnect_installation")
    const reset = useFrappePostCall("commit.api.github_connection.reset_connection")
    const details = installationsCall.data?.message
    const installations = details?.installations ?? []

    const confirmDisconnect = async () => {
        if (!disconnecting) return
        try {
            await disconnect.call({ installation_id: disconnecting.id })
            toast({ description: `${disconnecting.account || "GitHub account"} disconnected from Commit.` })
            setDisconnecting(null)
            await installationsCall.mutate()
            onChanged()
        } catch (error) {
            toast({ variant: "destructive", description: getErrorMessage(error as never) || "Could not disconnect the GitHub account." })
        }
    }

    const confirmReset = async () => {
        try {
            await reset.call({})
            toast({ description: "GitHub setup reset. You can now create a new App." })
            setResetOpen(false)
            onOpenChange(false)
            onChanged()
        } catch (error) {
            toast({ variant: "destructive", description: getErrorMessage(error as never) || "Could not reset GitHub setup." })
        }
    }

    return (
        <>
            <Dialog open={open} onOpenChange={onOpenChange}>
                <DialogContent className="max-w-2xl overflow-hidden p-0">
                    <DialogHeader className="border-b bg-muted/20 px-6 py-5">
                        <div className="flex items-start gap-3">
                            <span className="rounded-xl border bg-background p-2.5 shadow-sm"><Github className="h-5 w-5" /></span>
                            <div>
                                <DialogTitle>GitHub connections</DialogTitle>
                                <DialogDescription className="mt-1">Manage the accounts and organizations available to this Commit workspace.</DialogDescription>
                            </div>
                        </div>
                    </DialogHeader>
                    <div className="max-h-[58vh] space-y-4 overflow-y-auto px-6 py-5">
                        {installationsCall.error && <ErrorBanner error={installationsCall.error} />}
                        {installationsCall.isLoading && <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading connections…</div>}
                        {!installationsCall.isLoading && details && (
                            <>
                                <div className="flex flex-col gap-3 rounded-xl border bg-muted/20 p-4 sm:flex-row sm:items-center">
                                    <span className="rounded-lg bg-emerald-50 p-2 text-emerald-700"><ShieldCheck className="h-5 w-5" /></span>
                                    <div className="min-w-0 flex-1">
                                        <div className="truncate text-sm font-semibold">{details.app_name || "Commit GitHub App"}</div>
                                        <div className="text-xs text-muted-foreground">{installations.length} connected account{installations.length === 1 ? "" : "s"}</div>
                                    </div>
                                    {details.app_url && <Button asChild size="sm" variant="outline"><a href={details.app_url} target="_blank" rel="noreferrer">App settings <ExternalLink className="ml-2 h-3.5 w-3.5" /></a></Button>}
                                </div>
                                <div className="space-y-2">
                                    <div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Connected accounts</h3><Badge variant="secondary">{installations.length}</Badge></div>
                                    {installations.length ? installations.map(installation => {
                                        const AccountIcon = installation.account_type === "Organization" ? Building2 : UserRound
                                        return (
                                            <div key={installation.id} className="flex items-center gap-3 rounded-xl border bg-background p-4 shadow-sm">
                                                <span className="rounded-lg bg-muted p-2"><AccountIcon className="h-4 w-4" /></span>
                                                <div className="min-w-0 flex-1">
                                                    <div className="truncate text-sm font-semibold">{installation.account || "GitHub account"}</div>
                                                    <div className="mt-0.5 flex flex-wrap gap-2 text-xs text-muted-foreground">
                                                        <span>{installation.account_type || "Account"}</span><span>•</span>
                                                        <span>{installation.repository_selection === "all" ? "All repositories" : "Selected repositories"}</span><span>•</span>
                                                        <span>{installation.project_count || 0} Commit organization{installation.project_count === 1 ? "" : "s"}</span>
                                                    </div>
                                                </div>
                                                <Button size="sm" variant="ghost" className="text-destructive hover:text-destructive" onClick={() => setDisconnecting(installation)}><Trash2 className="mr-2 h-4 w-4" />Disconnect</Button>
                                            </div>
                                        )
                                    }) : <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">No GitHub accounts are connected to this App.</div>}
                                </div>
                                <div className="grid gap-3 sm:grid-cols-2">
                                    <Button variant="outline" className="h-auto justify-start gap-3 p-4 text-left" onClick={() => { onOpenChange(false); onAddAccount() }}>
                                        <Plus className="h-5 w-5" /><span><span className="block font-semibold">Add account or organization</span><span className="block text-xs font-normal text-muted-foreground">Install this App on another GitHub account.</span></span>
                                    </Button>
                                    <Button variant="outline" className="h-auto justify-start gap-3 p-4 text-left" onClick={() => { onOpenChange(false); onManageRepositories() }}>
                                        <Github className="h-5 w-5" /><span><span className="block font-semibold">Manage repositories</span><span className="block text-xs font-normal text-muted-foreground">Import repositories available to connected accounts.</span></span>
                                    </Button>
                                </div>
                                <div className="rounded-xl border border-amber-200 bg-amber-50/60 p-4">
                                    <div className="flex items-start gap-3"><RefreshCcw className="mt-0.5 h-4 w-4 text-amber-700" /><div className="flex-1"><div className="text-sm font-semibold text-amber-950">Need a different GitHub App?</div><p className="mt-1 text-xs leading-5 text-amber-900/70">Resetting removes local credentials and connections. Existing projects remain, and the App is not deleted from GitHub.</p><Button size="sm" variant="outline" className="mt-3 border-amber-300 bg-white" onClick={() => setResetOpen(true)}>Reset GitHub setup</Button></div></div>
                                </div>
                            </>
                        )}
                    </div>
                    <DialogFooter className="border-t bg-muted/20 px-6 py-4"><Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button></DialogFooter>
                </DialogContent>
            </Dialog>

            <AlertDialog open={Boolean(disconnecting)} onOpenChange={open => !open && setDisconnecting(null)}>
                <AlertDialogContent>
                    <AlertDialogHeader><AlertDialogTitle>Disconnect {disconnecting?.account}?</AlertDialogTitle><AlertDialogDescription>This removes the installation from Commit. Imported projects remain, but private repository refreshes and GitHub checks for this account pause until it is reconnected.</AlertDialogDescription></AlertDialogHeader>
                    <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={confirmDisconnect}>{disconnect.loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Disconnect</AlertDialogAction></AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>

            <AlertDialog open={resetOpen} onOpenChange={setResetOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader><AlertDialogTitle>Reset the GitHub App connection?</AlertDialogTitle><AlertDialogDescription>Commit will forget the App credentials and all connected installations. Projects and scan history remain. The App itself remains in GitHub until you remove it there.</AlertDialogDescription></AlertDialogHeader>
                    <AlertDialogFooter><AlertDialogCancel>Cancel</AlertDialogCancel><AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" onClick={confirmReset}>{reset.loading && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}Reset connection</AlertDialogAction></AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </>
    )
}
