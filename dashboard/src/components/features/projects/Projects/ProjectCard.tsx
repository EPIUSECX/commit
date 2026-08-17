import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu"
import { AlertDialog } from "@/components/ui/alert-dialog"
import { Dialog } from "@radix-ui/react-dialog"
import { Activity, BrainCircuit, Braces, EllipsisVertical, ExternalLink, GitBranch, Github, ShieldAlert, Trash2 } from "lucide-react"
import { useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { KeyedMutator } from "swr"
import { isSystemManager } from "@/utils/roles"
import ManageBranchModal from "../Branch/ManageBranchModal"
import { ProjectData, ProjectWithBranch } from "../Projects"
import DeleteProjectModal from "./DeleteProjectModal"

export interface ProjectCardProps {
  project: ProjectWithBranch
  mutate: KeyedMutator<{ message: ProjectData[] }>
  orgName: string
  githubOrg: string
}

const statusStyle: Record<string, string> = {
  Completed: "border-emerald-200 bg-emerald-50 text-emerald-700",
  Running: "border-blue-200 bg-blue-50 text-blue-700",
  Queued: "border-amber-200 bg-amber-50 text-amber-700",
  Failed: "border-red-200 bg-red-50 text-red-700",
}

const ProjectCard = ({ project, mutate, orgName, githubOrg }: ProjectCardProps) => {
  const [openManageModal, setOpenManageModal] = useState(false)
  const [openDeleteDialogModal, setOpenDeleteDialogModal] = useState(false)
  const primaryBranch = project.branches.find(branch => branch.branch_name === project.default_branch) || project.branches[0]
  const intelligence = primaryBranch?.intelligence
  const appNameInitials = useMemo(() => project.display_name?.[0]?.toUpperCase() || "P", [project.display_name])
  const isCreateAccess = isSystemManager()

  return (
    <article className="group flex h-full flex-col overflow-hidden rounded-xl border bg-background shadow-sm transition-all hover:-translate-y-0.5 hover:border-gray-300 hover:shadow-md">
      <div className="flex items-start gap-4 p-5">
        <Avatar className="h-11 w-11 rounded-xl border bg-muted shadow-sm">
          <AvatarImage src={project.image} className="object-contain" />
          <AvatarFallback className="rounded-xl text-base font-semibold">{appNameInitials}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-base font-semibold">{project.display_name}</h3>
              <div className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><Github className="h-3.5 w-3.5" />{githubOrg}/{project.repo_name}</div>
            </div>
            {isCreateAccess && <DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" className="h-8 w-8 shrink-0"><EllipsisVertical className="h-4 w-4" /><span className="sr-only">Project actions</span></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem asChild><a href={`https://github.com/${githubOrg}/${project.repo_name}`} target="_blank" rel="noreferrer"><ExternalLink className="mr-2 h-4 w-4" />Open on GitHub</a></DropdownMenuItem><DropdownMenuItem onClick={() => setOpenManageModal(true)}><GitBranch className="mr-2 h-4 w-4" />Manage branches</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => setOpenDeleteDialogModal(true)}><Trash2 className="mr-2 h-4 w-4" />Delete project</DropdownMenuItem></DropdownMenuContent></DropdownMenu>}
          </div>
          <p className="mt-3 line-clamp-2 min-h-10 text-sm leading-5 text-muted-foreground">{project.description || "Repository intelligence and API governance workspace."}</p>
        </div>
      </div>

      <div className="grid grid-cols-3 border-y bg-muted/20">
        <div className="p-3 text-center"><div className="text-lg font-semibold">{project.branches.length}</div><div className="text-[11px] text-muted-foreground">Branches</div></div>
        <div className="border-x p-3 text-center"><div className="text-lg font-semibold">{intelligence?.risk_score ?? "—"}</div><div className="text-[11px] text-muted-foreground">Risk score</div></div>
        <div className="p-3 text-center"><div className="text-lg font-semibold">{intelligence?.finding_count ?? "—"}</div><div className="text-[11px] text-muted-foreground">Findings</div></div>
      </div>

      <div className="flex flex-wrap items-center gap-2 px-5 py-3">
        <Badge variant="outline" className={statusStyle[primaryBranch?.scan_status || ""] || ""}><Activity className="mr-1 h-3 w-3" />{primaryBranch?.scan_status || "Not scanned"}</Badge>
        {intelligence?.breaking_change_count ? <Badge variant="destructive"><ShieldAlert className="mr-1 h-3 w-3" />{intelligence.breaking_change_count} breaking</Badge> : null}
        {primaryBranch?.branch_name && <Badge variant="secondary"><GitBranch className="mr-1 h-3 w-3" />{primaryBranch.branch_name}</Badge>}
      </div>

      <div className="mt-auto grid grid-cols-2 gap-2 px-5 pb-5 pt-1">
        {primaryBranch ? <Button asChild><Link to={`/intelligence/${primaryBranch.name}`}><BrainCircuit className="mr-2 h-4 w-4" />Intelligence</Link></Button> : <Button disabled><BrainCircuit className="mr-2 h-4 w-4" />Intelligence</Button>}
        {primaryBranch ? <Button asChild variant="outline"><Link to={`/project-viewer/${primaryBranch.name}`}><Braces className="mr-2 h-4 w-4" />API Explorer</Link></Button> : <Button variant="outline" disabled><Braces className="mr-2 h-4 w-4" />API Explorer</Button>}
        <Button variant="ghost" className="col-span-2" onClick={() => setOpenManageModal(true)}><GitBranch className="mr-2 h-4 w-4" />Manage {project.branches.length} branch{project.branches.length === 1 ? "" : "es"}</Button>
      </div>

      <AlertDialog open={openDeleteDialogModal} onOpenChange={setOpenDeleteDialogModal}><DeleteProjectModal project={project} mutate={mutate} /></AlertDialog>
      <Dialog open={openManageModal} onOpenChange={setOpenManageModal}><ManageBranchModal branches={project.branches} mutate={mutate} setOpenManageModal={setOpenManageModal} /></Dialog>
    </article>
  )
}

export default ProjectCard
