import { DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { ProjectData } from "../Projects"
import { Button } from "@/components/ui/button"
import { KeyedMutator } from "swr"
import { CommitProjectBranch } from "@/types/commit/CommitProjectBranch"
import ManageBranchItem from "./ManageBranchItem"

export interface ManageBranchModalProps {
    branches: CommitProjectBranch[]
    mutate: KeyedMutator<{ message: ProjectData[]; }>
    setOpenManageModal: React.Dispatch<React.SetStateAction<boolean>>
}


const ManageBranchModal = ({ branches, mutate, setOpenManageModal }: ManageBranchModalProps) => {

    return (
        <DialogContent className="w-[94vw] max-w-4xl overflow-hidden p-0">
            <DialogHeader className="border-b bg-muted/20 px-6 py-5 text-left">
                <DialogTitle>Manage branches</DialogTitle>
                <p className="text-sm text-muted-foreground">Refresh repository code, review intelligence, and control automatic scan frequency.</p>
            </DialogHeader>
            <ul role="list" className="max-h-[62vh] space-y-3 overflow-y-auto px-6 py-5">
                {branches?.map((branch: CommitProjectBranch) => {
                    return (
                        <ManageBranchItem key={branch.name} branch={branch} mutate={mutate} />
                    )
                }
                )}
            </ul>
            <DialogFooter className="border-t bg-muted/20 px-6 py-4">
                <Button variant="outline" onClick={() => setOpenManageModal(false)}>
                    Close
                </Button>
            </DialogFooter>
        </DialogContent>
    )
}


export default ManageBranchModal
