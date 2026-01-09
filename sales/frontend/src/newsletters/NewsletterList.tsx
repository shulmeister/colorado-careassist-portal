import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Mail, Send, Eye, CheckCircle2, XCircle, Loader2 } from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

type BrevoList = {
  id: number;
  name: string;
  uniqueSubscribers: number;
  folderId: number;
};

type NewsletterTemplate = {
  name: string;
  file: string;
  audience: "clients" | "referral_sources";
};

const templates: NewsletterTemplate[] = [
  {
    name: "Clients Newsletter",
    file: "newsletter_january_2025_clients.html",
    audience: "clients",
  },
  {
    name: "Referral Sources Newsletter",
    file: "newsletter_january_2025_referral_sources.html",
    audience: "referral_sources",
  },
];

export const NewsletterList = () => {
  const [lists, setLists] = useState<BrevoList[]>([]);
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState<number | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<{
    success: boolean;
    message?: string;
    error?: string;
  } | null>(null);
  const [sendDialog, setSendDialog] = useState<{
    open: boolean;
    listId: number | null;
    listName: string;
    template: NewsletterTemplate | null;
    subject: string;
    htmlContent: string;
  }>({
    open: false,
    listId: null,
    listName: "",
    template: null,
    subject: "Colorado CareAssist Newsletter - January 2025",
    htmlContent: "",
  });
  const [previewDialog, setPreviewDialog] = useState<{
    open: boolean;
    html: string;
  }>({
    open: false,
    html: "",
  });

  useEffect(() => {
    checkConnection();
    fetchLists();
  }, []);

  const checkConnection = async () => {
    try {
      const response = await fetch("/api/brevo/test", {
        credentials: "include",
      });
      const data = await response.json();
      setConnectionStatus(data);
      if (!data.success) {
        toast.error(data.error || "Unable to connect to Brevo");
      }
    } catch (error) {
      console.error("Connection check error:", error);
      setConnectionStatus({
        success: false,
        error: "Failed to check connection",
      });
    }
  };

  const fetchLists = async () => {
    try {
      setLoading(true);
      const response = await fetch("/api/brevo/lists", {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Failed to fetch lists");
      }
      const data = await response.json();
      if (data.success && data.lists) {
        setLists(data.lists);
      } else {
        throw new Error(data.error || "Failed to fetch lists");
      }
    } catch (error) {
      console.error("Error fetching lists:", error);
      toast.error("Failed to load Brevo lists");
    } finally {
      setLoading(false);
    }
  };

  const loadTemplate = async (template: NewsletterTemplate) => {
    try {
      const response = await fetch(`/api/brevo/newsletter-template/${template.file}`, {
        credentials: "include",
      });
      if (!response.ok) {
        throw new Error("Template not found");
      }
      const data = await response.json();
      if (data.success && data.html) {
        return data.html;
      }
      throw new Error("Invalid template response");
    } catch (error) {
      console.error("Error loading template:", error);
      toast.error("Could not load template. Please check if template file exists.");
      return null;
    }
  };

  const handlePreview = async (template: NewsletterTemplate) => {
    const html = await loadTemplate(template);
    if (html) {
      setPreviewDialog({ open: true, html });
    }
  };

  const handleSendClick = async (list: BrevoList, template: NewsletterTemplate) => {
    const html = await loadTemplate(template);
    if (!html) return;

    setSendDialog({
      open: true,
      listId: list.id,
      listName: list.name,
      template,
      subject: `Colorado CareAssist Newsletter - ${new Date().toLocaleDateString("en-US", { month: "long", year: "numeric" })}`,
      htmlContent: html,
    });
  };

  const handleSend = async () => {
    if (!sendDialog.listId || !sendDialog.htmlContent) return;

    try {
      setSending(sendDialog.listId);
      const response = await fetch("/api/brevo/send-newsletter", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify({
          list_id: sendDialog.listId,
          subject: sendDialog.subject,
          html_content: sendDialog.htmlContent,
          use_template: false, // We're providing HTML directly
        }),
      });

      const data = await response.json();
      if (data.success) {
        toast.success(`Newsletter sent! Successfully sent to ${data.sent || 0} recipients in ${data.list_name}`);
        setSendDialog({ ...sendDialog, open: false });
      } else {
        throw new Error(data.error || "Failed to send newsletter");
      }
    } catch (error) {
      console.error("Send error:", error);
      toast.error(error instanceof Error ? error.message : "Failed to send newsletter");
    } finally {
      setSending(null);
    }
  };

  const getListForAudience = (audience: "clients" | "referral_sources"): BrevoList | null => {
    if (audience === "clients") {
      return lists.find((l) => l.name.toLowerCase().includes("client")) || null;
    } else {
      return (
        lists.find((l) => l.name.toLowerCase().includes("referral")) || null
      );
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Newsletter Management</h1>
        <p className="text-muted-foreground mt-2">
          Manage and send newsletters to your Brevo contact lists
        </p>
      </div>

      {connectionStatus && (
        <Alert variant={connectionStatus.success ? "default" : "destructive"}>
          {connectionStatus.success ? (
            <CheckCircle2 className="h-4 w-4" />
          ) : (
            <XCircle className="h-4 w-4" />
          )}
          <AlertTitle>
            {connectionStatus.success ? "Connected to Brevo" : "Brevo Connection Error"}
          </AlertTitle>
          <AlertDescription>
            {connectionStatus.success
              ? connectionStatus.message || "Successfully connected"
              : connectionStatus.error || "Unable to connect"}
          </AlertDescription>
        </Alert>
      )}

      <div className="grid gap-6 md:grid-cols-2">
        {templates.map((template) => {
          const targetList = getListForAudience(template.audience);
          return (
            <Card key={template.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="flex items-center gap-2">
                      <Mail className="h-5 w-5" />
                      {template.name}
                    </CardTitle>
                    <CardDescription className="mt-2">
                      {template.audience === "clients"
                        ? "For clients and customers"
                        : "For referral partners and sources"}
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                {targetList ? (
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Target List:</span>
                      <Badge variant="secondary">{targetList.name}</Badge>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Contacts:</span>
                      <span className="font-semibold">{targetList.uniqueSubscribers}</span>
                    </div>
                  </div>
                ) : (
                  <Alert variant="destructive">
                    <AlertDescription>
                      No matching list found for {template.audience === "clients" ? "clients" : "referral sources"}
                    </AlertDescription>
                  </Alert>
                )}

                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePreview(template)}
                    className="flex-1"
                  >
                    <Eye className="h-4 w-4 mr-2" />
                    Preview
                  </Button>
                  <Button
                    size="sm"
                    onClick={() => targetList && handleSendClick(targetList, template)}
                    disabled={!targetList || sending !== null}
                    className="flex-1"
                  >
                    {sending === targetList?.id ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      <>
                        <Send className="h-4 w-4 mr-2" />
                        Send
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Available Brevo Lists</CardTitle>
          <CardDescription>All contact lists in your Brevo account</CardDescription>
        </CardHeader>
        <CardContent>
          {lists.length === 0 ? (
            <p className="text-muted-foreground">No lists found</p>
          ) : (
            <div className="space-y-2">
              {lists.map((list) => (
                <div
                  key={list.id}
                  className="flex items-center justify-between p-3 border rounded-lg"
                >
                  <div>
                    <div className="font-medium">{list.name}</div>
                    <div className="text-sm text-muted-foreground">ID: {list.id}</div>
                  </div>
                  <Badge variant="outline">{list.uniqueSubscribers} contacts</Badge>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preview Dialog */}
      <Dialog open={previewDialog.open} onOpenChange={(open) => setPreviewDialog({ ...previewDialog, open })}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto">
          <DialogHeader>
            <DialogTitle>Newsletter Preview</DialogTitle>
            <DialogDescription>
              Preview of the newsletter template
            </DialogDescription>
          </DialogHeader>
          <div
            className="border rounded-lg p-4 bg-white"
            dangerouslySetInnerHTML={{ __html: previewDialog.html }}
          />
        </DialogContent>
      </Dialog>

      {/* Send Dialog */}
      <Dialog open={sendDialog.open} onOpenChange={(open) => setSendDialog({ ...sendDialog, open })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Send Newsletter</DialogTitle>
            <DialogDescription>
              Send newsletter to {sendDialog.listName} ({sendDialog.listId ? lists.find(l => l.id === sendDialog.listId)?.uniqueSubscribers : 0} contacts)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="subject">Subject Line</Label>
              <Input
                id="subject"
                value={sendDialog.subject}
                onChange={(e) => setSendDialog({ ...sendDialog, subject: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <Label>Template</Label>
              <div className="p-3 bg-muted rounded-md">
                {sendDialog.template?.name}
              </div>
            </div>
            <Alert>
              <AlertDescription>
                This will send the newsletter to all {lists.find(l => l.id === sendDialog.listId)?.uniqueSubscribers || 0} contacts in the list. This action cannot be undone.
              </AlertDescription>
            </Alert>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendDialog({ ...sendDialog, open: false })}>
              Cancel
            </Button>
            <Button onClick={handleSend} disabled={sending !== null || !sendDialog.subject}>
              {sending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Sending...
                </>
              ) : (
                <>
                  <Send className="h-4 w-4 mr-2" />
                  Send Newsletter
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

