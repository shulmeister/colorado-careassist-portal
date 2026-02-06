import { Plus, Check, Clock, User } from "lucide-react";
import { useState } from "react";
import {
  useDataProvider,
  useGetIdentity,
  useNotify,
  useRefresh,
} from "ra-core";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Checkbox } from "@/components/ui/checkbox";
import { formatDistance } from "date-fns";

import { getAssigneeChoices, getAssigneeLabel } from "../tasks/assignees";
import type { Identifier } from "ra-core";

type CompanyTask = {
  id: number;
  company_id: number;
  title: string;
  description?: string;
  due_date?: string;
  status: string;
  assigned_to?: string;
  created_at?: string;
};

export const CompanyTasksList = ({ companyId }: { companyId: Identifier }) => {
  const { identity } = useGetIdentity();
  const dataProvider = useDataProvider();
  const notify = useNotify();
  const refresh = useRefresh();
  const [tasks, setTasks] = useState<CompanyTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [addDialogOpen, setAddDialogOpen] = useState(false);
  const [newTask, setNewTask] = useState({
    title: "",
    description: "",
    due_date: new Date().toISOString().slice(0, 10),
    assigned_to: (identity as any)?.email ?? "",
  });

  // Fetch tasks for this company
  const fetchTasks = async () => {
    try {
      const response = await fetch(
        `/sales/admin/tasks?contact_id=${companyId}&sort=created_at&order=DESC`
      );
      if (response.ok) {
        const data = await response.json();
        setTasks(data.data || []);
      }
    } catch (error) {
      console.error("Failed to fetch tasks:", error);
    } finally {
      setLoading(false);
    }
  };

  // Load tasks on mount
  useState(() => {
    fetchTasks();
  });

  const handleAddTask = async () => {
    try {
      const response = await fetch("/sales/admin/tasks", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          contact_id: companyId, // API uses contact_id for company tasks
          text: newTask.title,
          type: "Follow-up",
          due_date: newTask.due_date,
          assigned_to: newTask.assigned_to,
        }),
      });

      if (response.ok) {
        notify("Task added successfully");
        setAddDialogOpen(false);
        setNewTask({
          title: "",
          description: "",
          due_date: new Date().toISOString().slice(0, 10),
          assigned_to: (identity as any)?.email ?? "",
        });
        fetchTasks();
      } else {
        notify("Failed to add task", { type: "error" });
      }
    } catch (error) {
      notify("Failed to add task", { type: "error" });
    }
  };

  const handleToggleComplete = async (task: CompanyTask) => {
    try {
      const newStatus = task.status === "completed" ? "pending" : "completed";
      const response = await fetch(`/sales/admin/tasks/${task.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...task,
          status: newStatus,
          done_date: newStatus === "completed" ? new Date().toISOString() : null,
        }),
      });

      if (response.ok) {
        fetchTasks();
      }
    } catch (error) {
      notify("Failed to update task", { type: "error" });
    }
  };

  const meEmail = (identity as any)?.email;
  const assigneeChoices = getAssigneeChoices(meEmail);

  if (loading) {
    return <div className="text-muted-foreground p-4">Loading tasks...</div>;
  }

  const pendingTasks = tasks.filter((t) => t.status !== "completed");
  const completedTasks = tasks.filter((t) => t.status === "completed");

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">Tasks ({tasks.length})</h3>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setAddDialogOpen(true)}
        >
          <Plus className="w-4 h-4 mr-1" />
          Add Task
        </Button>
      </div>

      {tasks.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            No tasks yet. Add one to get started!
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {pendingTasks.map((task) => (
            <TaskItem
              key={task.id}
              task={task}
              onToggle={() => handleToggleComplete(task)}
              meEmail={meEmail}
            />
          ))}
          {completedTasks.length > 0 && (
            <>
              <div className="text-sm text-muted-foreground mt-4 mb-2">
                Completed ({completedTasks.length})
              </div>
              {completedTasks.slice(0, 5).map((task) => (
                <TaskItem
                  key={task.id}
                  task={task}
                  onToggle={() => handleToggleComplete(task)}
                  meEmail={meEmail}
                />
              ))}
            </>
          )}
        </div>
      )}

      {/* Add Task Dialog */}
      <Dialog open={addDialogOpen} onOpenChange={setAddDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Task</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-4">
            <div>
              <Label htmlFor="title">Task Description</Label>
              <Input
                id="title"
                value={newTask.title}
                onChange={(e) =>
                  setNewTask({ ...newTask, title: e.target.value })
                }
                placeholder="What needs to be done?"
              />
            </div>
            <div>
              <Label htmlFor="due_date">Due Date</Label>
              <Input
                id="due_date"
                type="date"
                value={newTask.due_date}
                onChange={(e) =>
                  setNewTask({ ...newTask, due_date: e.target.value })
                }
              />
            </div>
            <div>
              <Label htmlFor="assigned_to">Assign To</Label>
              <Select
                value={newTask.assigned_to}
                onValueChange={(value) =>
                  setNewTask({ ...newTask, assigned_to: value })
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Select assignee" />
                </SelectTrigger>
                <SelectContent>
                  {assigneeChoices.map((choice) => (
                    <SelectItem key={choice.id} value={choice.id}>
                      {choice.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleAddTask} disabled={!newTask.title}>
              Add Task
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

const TaskItem = ({
  task,
  onToggle,
  meEmail,
}: {
  task: CompanyTask;
  onToggle: () => void;
  meEmail?: string;
}) => {
  const isCompleted = task.status === "completed";
  const isOverdue =
    !isCompleted && task.due_date && new Date(task.due_date) < new Date();

  return (
    <Card
      className={`${isCompleted ? "opacity-60" : ""} ${isOverdue ? "border-red-500" : ""}`}
    >
      <CardContent className="py-3 flex items-start gap-3">
        <Checkbox
          checked={isCompleted}
          onCheckedChange={onToggle}
          className="mt-1"
        />
        <div className="flex-1 min-w-0">
          <div
            className={`font-medium ${isCompleted ? "line-through text-muted-foreground" : ""}`}
          >
            {task.title}
          </div>
          <div className="flex gap-3 text-xs text-muted-foreground mt-1">
            {task.due_date && (
              <span
                className={`flex items-center gap-1 ${isOverdue ? "text-red-500" : ""}`}
              >
                <Clock className="w-3 h-3" />
                {isOverdue ? "Overdue: " : ""}
                {formatDistance(new Date(task.due_date), new Date(), {
                  addSuffix: true,
                })}
              </span>
            )}
            {task.assigned_to && (
              <span className="flex items-center gap-1">
                <User className="w-3 h-3" />
                {getAssigneeLabel(task.assigned_to, meEmail)}
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

