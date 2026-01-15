import { useEffect, useState, useCallback } from "react";
import { ShiftFillingNav } from "./ShiftFillingNav";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type Shift = {
  id: string;
  client_id: string;
  client_name: string;
  client_city: string;
  date: string;
  start_time: string;
  end_time: string;
  duration_hours: number;
  is_urgent: boolean;
  hours_until_start: number;
  status: string;
  original_caregiver_id: string | null;
};

type Caregiver = {
  id: string;
  name: string;
  phone: string;
  city: string;
  hours_available: number;
  is_near_overtime: boolean;
  avg_rating: number;
  reliability_score: number;
  response_rate: number;
  is_active: boolean;
};

type Match = {
  caregiver_id: string;
  caregiver_name: string;
  phone: string;
  score: number;
  tier: number;
  reasons: string[];
};

type Campaign = {
  id: string;
  shift_id: string;
  status: string;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  total_contacted: number;
  total_responded: number;
  total_accepted: number;
  total_declined: number;
  winning_caregiver_id: string | null;
  winning_caregiver_name: string | null;
  escalated: boolean;
  escalation_reason: string;
};

type EngineStatus = {
  status: string;
  sms_enabled: boolean;
  active_campaigns: number;
  service: string;
};

export const ShiftFillingDashboard = () => {
  const [shifts, setShifts] = useState<Shift[]>([]);
  const [caregivers, setCaregivers] = useState<Caregiver[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [engineStatus, setEngineStatus] = useState<EngineStatus | null>(null);
  const [selectedShift, setSelectedShift] = useState<Shift | null>(null);
  const [matches, setMatches] = useState<Match[]>([]);
  const [matchLoading, setMatchLoading] = useState(false);
  const [calloffDialogOpen, setCalloffDialogOpen] = useState(false);
  const [calloffShift, setCalloffShift] = useState<Shift | null>(null);
  const [calloffCaregiver, setCalloffCaregiver] = useState<string>("");
  const [calloffReason, setCalloffReason] = useState<string>("");
  const [processing, setProcessing] = useState(false);
  const [demoResult, setDemoResult] = useState<any>(null);
  const [responseDialogOpen, setResponseDialogOpen] = useState(false);
  const [responseCampaignId, setResponseCampaignId] = useState<string>("");
  const [responsePhone, setResponsePhone] = useState<string>("");
  const [responseMessage, setResponseMessage] = useState<string>("");

  const fetchData = useCallback(async () => {
    try {
      const [statusRes, shiftsRes, caregiversRes, campaignsRes] = await Promise.all([
        fetch("/sales/api/shift-filling/status", { credentials: "include" }),
        fetch("/sales/api/shift-filling/open-shifts", { credentials: "include" }),
        fetch("/sales/api/shift-filling/caregivers", { credentials: "include" }),
        fetch("/sales/api/shift-filling/campaigns", { credentials: "include" }),
      ]);

      if (statusRes.ok) setEngineStatus(await statusRes.json());
      if (shiftsRes.ok) setShifts(await shiftsRes.json());
      if (caregiversRes.ok) setCaregivers(await caregiversRes.json());
      if (campaignsRes.ok) {
        const data = await campaignsRes.json();
        setCampaigns(data.active_campaigns || []);
      }
    } catch (error) {
      console.error("Error fetching data:", error);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10 seconds
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleFindMatches = async (shift: Shift) => {
    setSelectedShift(shift);
    setMatchLoading(true);
    setMatches([]);

    try {
      const res = await fetch(`/sales/api/shift-filling/match/${shift.id}`, {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setMatches(data.matches || []);
      }
    } catch (error) {
      console.error("Error finding matches:", error);
    } finally {
      setMatchLoading(false);
    }
  };

  const handleProcessCalloff = async () => {
    if (!calloffShift || !calloffCaregiver) return;
    setProcessing(true);

    try {
      const res = await fetch("/sales/api/shift-filling/calloff", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          shift_id: calloffShift.id,
          caregiver_id: calloffCaregiver,
          reason: calloffReason,
        }),
      });

      if (res.ok) {
        const result = await res.json();
        alert(`Campaign started! ${result.total_contacted} caregivers contacted.`);
        setCalloffDialogOpen(false);
        setCalloffShift(null);
        setCalloffCaregiver("");
        setCalloffReason("");
        fetchData();
      }
    } catch (error) {
      console.error("Error processing calloff:", error);
      alert("Error processing calloff");
    } finally {
      setProcessing(false);
    }
  };

  const handleRunDemo = async () => {
    setProcessing(true);
    setDemoResult(null);

    try {
      const res = await fetch("/sales/api/shift-filling/demo", {
        method: "POST",
        credentials: "include",
      });

      if (res.ok) {
        const result = await res.json();
        setDemoResult(result);
        fetchData();
      }
    } catch (error) {
      console.error("Error running demo:", error);
    } finally {
      setProcessing(false);
    }
  };

  const handleSimulateResponse = async () => {
    if (!responseCampaignId || !responsePhone || !responseMessage) return;
    setProcessing(true);

    try {
      const res = await fetch("/sales/api/shift-filling/simulate-response", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          campaign_id: responseCampaignId,
          phone: responsePhone,
          message_text: responseMessage,
        }),
      });

      if (res.ok) {
        const result = await res.json();
        alert(`Response processed: ${result.action || result.response_type}`);
        setResponseDialogOpen(false);
        setResponseCampaignId("");
        setResponsePhone("");
        setResponseMessage("");
        fetchData();
      }
    } catch (error) {
      console.error("Error simulating response:", error);
    } finally {
      setProcessing(false);
    }
  };

  const getTierBadge = (tier: number) => {
    switch (tier) {
      case 1:
        return <Badge className="bg-green-600">Tier 1</Badge>;
      case 2:
        return <Badge className="bg-yellow-600">Tier 2</Badge>;
      default:
        return <Badge variant="secondary">Tier 3</Badge>;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "filled":
        return <Badge className="bg-green-600">Filled</Badge>;
      case "in_progress":
        return <Badge className="bg-blue-600">In Progress</Badge>;
      case "escalated":
        return <Badge variant="destructive">Escalated</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <ShiftFillingNav />

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">
            AI-Powered Shift Filling
          </h1>
          <p className="text-muted-foreground text-sm">
            Automatically find replacement caregivers when shifts become open
          </p>
        </div>
        <div className="flex gap-2">
          <Button onClick={handleRunDemo} disabled={processing}>
            {processing ? "Running..." : "Run Demo"}
          </Button>
          <Button
            variant="outline"
            onClick={() => setResponseDialogOpen(true)}
            disabled={campaigns.length === 0}
          >
            Simulate Response
          </Button>
        </div>
      </div>

      {/* Engine Status */}
      {engineStatus && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <Card>
            <CardContent className="p-4">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-xs text-muted-foreground">Engine Status</p>
                  <p className="text-lg font-bold text-green-600">
                    {engineStatus.status === "active" ? "Active" : "Inactive"}
                  </p>
                </div>
                <div className="text-2xl">🤖</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-xs text-muted-foreground">SMS Service</p>
                  <p className={`text-lg font-bold ${engineStatus.sms_enabled ? "text-green-600" : "text-yellow-600"}`}>
                    {engineStatus.sms_enabled ? "Connected" : "Mock Mode"}
                  </p>
                </div>
                <div className="text-2xl">📱</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-xs text-muted-foreground">Open Shifts</p>
                  <p className="text-lg font-bold">{shifts.length}</p>
                </div>
                <div className="text-2xl">📋</div>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="flex justify-between items-center">
                <div>
                  <p className="text-xs text-muted-foreground">Active Campaigns</p>
                  <p className="text-lg font-bold">{engineStatus.active_campaigns}</p>
                </div>
                <div className="text-2xl">🚀</div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Demo Result */}
      {demoResult && (
        <Alert className="mb-6 border-green-500 bg-green-50 dark:bg-green-950">
          <AlertTitle className="text-green-700 dark:text-green-300">
            Demo Completed Successfully!
          </AlertTitle>
          <AlertDescription className="text-green-600 dark:text-green-400">
            Shift for <strong>{demoResult.shift?.client}</strong> on {demoResult.shift?.date}{" "}
            was filled by <strong>{demoResult.winner}</strong>.{" "}
            {demoResult.matches_found} matches found, {demoResult.caregivers_contacted} contacted.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Open Shifts */}
        <Card>
          <CardHeader>
            <CardTitle>Open Shifts</CardTitle>
            <CardDescription>
              Shifts that need to be filled
            </CardDescription>
          </CardHeader>
          <CardContent>
            {shifts.length === 0 ? (
              <p className="text-muted-foreground text-sm py-4">
                No open shifts at this time.
              </p>
            ) : (
              <div className="space-y-3">
                {shifts.map((shift) => (
                  <div
                    key={shift.id}
                    className={`p-3 rounded-lg border ${
                      shift.is_urgent ? "border-red-500 bg-red-50 dark:bg-red-950" : "border-border"
                    }`}
                  >
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{shift.client_name}</span>
                          {shift.is_urgent && (
                            <Badge variant="destructive" className="text-xs">
                              URGENT
                            </Badge>
                          )}
                        </div>
                        <p className="text-sm text-muted-foreground">
                          {shift.client_city} • {shift.date}
                        </p>
                        <p className="text-sm text-muted-foreground">
                          {shift.start_time} - {shift.end_time} ({shift.duration_hours}h)
                        </p>
                      </div>
                      <div className="flex flex-col gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleFindMatches(shift)}
                        >
                          Find Matches
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => {
                            setCalloffShift(shift);
                            setCalloffDialogOpen(true);
                          }}
                        >
                          Process Calloff
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Caregiver Matches */}
        <Card>
          <CardHeader>
            <CardTitle>
              Caregiver Matches
              {selectedShift && (
                <span className="text-sm font-normal text-muted-foreground ml-2">
                  for {selectedShift.client_name}
                </span>
              )}
            </CardTitle>
            <CardDescription>
              Ranked by match score (100 point scale)
            </CardDescription>
          </CardHeader>
          <CardContent>
            {matchLoading ? (
              <div className="py-8 text-center">
                <div className="animate-spin text-2xl mb-2">⏳</div>
                <p className="text-muted-foreground">Finding matches...</p>
              </div>
            ) : matches.length === 0 ? (
              <p className="text-muted-foreground text-sm py-4">
                Select a shift to find matching caregivers.
              </p>
            ) : (
              <div className="space-y-3">
                {matches.map((match, idx) => (
                  <div
                    key={match.caregiver_id}
                    className="p-3 rounded-lg border border-border"
                  >
                    <div className="flex justify-between items-start mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-lg font-bold text-muted-foreground">
                          #{idx + 1}
                        </span>
                        <span className="font-medium">{match.caregiver_name}</span>
                        {getTierBadge(match.tier)}
                      </div>
                      <div className="text-right">
                        <div className="text-lg font-bold">{match.score.toFixed(0)}</div>
                        <Progress value={match.score} className="w-20 h-2" />
                      </div>
                    </div>
                    <p className="text-xs text-muted-foreground">{match.phone}</p>
                    <div className="mt-2 space-y-1">
                      {match.reasons.slice(0, 3).map((reason, i) => (
                        <p key={i} className="text-xs text-muted-foreground">
                          {reason}
                        </p>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Active Campaigns */}
      {campaigns.length > 0 && (
        <Card className="mt-6">
          <CardHeader>
            <CardTitle>Active Campaigns</CardTitle>
            <CardDescription>
              Ongoing shift filling outreach campaigns
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Campaign ID</TableHead>
                  <TableHead>Shift</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Contacted</TableHead>
                  <TableHead>Responded</TableHead>
                  <TableHead>Accepted</TableHead>
                  <TableHead>Winner</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {campaigns.map((campaign) => (
                  <TableRow key={campaign.id}>
                    <TableCell className="font-mono text-xs">
                      {campaign.id.substring(0, 8)}...
                    </TableCell>
                    <TableCell>{campaign.shift_id}</TableCell>
                    <TableCell>{getStatusBadge(campaign.status)}</TableCell>
                    <TableCell>{campaign.total_contacted}</TableCell>
                    <TableCell>{campaign.total_responded}</TableCell>
                    <TableCell>{campaign.total_accepted}</TableCell>
                    <TableCell>
                      {campaign.winning_caregiver_name || "-"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {/* Available Caregivers */}
      <Card className="mt-6">
        <CardHeader>
          <CardTitle>Available Caregivers</CardTitle>
          <CardDescription>
            Active caregivers in the system
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>City</TableHead>
                <TableHead>Hours Available</TableHead>
                <TableHead>Rating</TableHead>
                <TableHead>Reliability</TableHead>
                <TableHead>Response Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {caregivers.map((cg) => (
                <TableRow key={cg.id}>
                  <TableCell className="font-medium">{cg.name}</TableCell>
                  <TableCell>{cg.city}</TableCell>
                  <TableCell>
                    {cg.hours_available.toFixed(0)}h
                    {cg.is_near_overtime && (
                      <Badge variant="outline" className="ml-2 text-xs">
                        Near OT
                      </Badge>
                    )}
                  </TableCell>
                  <TableCell>⭐ {cg.avg_rating.toFixed(1)}</TableCell>
                  <TableCell>{(cg.reliability_score * 100).toFixed(0)}%</TableCell>
                  <TableCell>{(cg.response_rate * 100).toFixed(0)}%</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Calloff Dialog */}
      <Dialog open={calloffDialogOpen} onOpenChange={setCalloffDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Process Calloff</DialogTitle>
            <DialogDescription>
              Record a caregiver calloff and start automated shift filling.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label>Shift</Label>
              <p className="text-sm text-muted-foreground">
                {calloffShift?.client_name} - {calloffShift?.date}{" "}
                {calloffShift?.start_time}-{calloffShift?.end_time}
              </p>
            </div>
            <div>
              <Label htmlFor="caregiver">Original Caregiver</Label>
              <Select value={calloffCaregiver} onValueChange={setCalloffCaregiver}>
                <SelectTrigger>
                  <SelectValue placeholder="Select caregiver" />
                </SelectTrigger>
                <SelectContent>
                  {caregivers.map((cg) => (
                    <SelectItem key={cg.id} value={cg.id}>
                      {cg.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="reason">Calloff Reason</Label>
              <Input
                id="reason"
                value={calloffReason}
                onChange={(e) => setCalloffReason(e.target.value)}
                placeholder="e.g., Sick, Car trouble, Emergency"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCalloffDialogOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleProcessCalloff} disabled={processing || !calloffCaregiver}>
              {processing ? "Processing..." : "Start Outreach"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Simulate Response Dialog */}
      <Dialog open={responseDialogOpen} onOpenChange={setResponseDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Simulate Caregiver Response</DialogTitle>
            <DialogDescription>
              Test the response handling by simulating an SMS reply.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div>
              <Label htmlFor="campaign">Campaign</Label>
              <Select value={responseCampaignId} onValueChange={setResponseCampaignId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select campaign" />
                </SelectTrigger>
                <SelectContent>
                  {campaigns.map((c) => (
                    <SelectItem key={c.id} value={c.id}>
                      {c.id.substring(0, 8)}... - {c.shift_id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label htmlFor="phone">Caregiver Phone</Label>
              <Input
                id="phone"
                value={responsePhone}
                onChange={(e) => setResponsePhone(e.target.value)}
                placeholder="e.g., 720-555-0001"
              />
            </div>
            <div>
              <Label htmlFor="message">Response Message</Label>
              <Input
                id="message"
                value={responseMessage}
                onChange={(e) => setResponseMessage(e.target.value)}
                placeholder="e.g., Yes, I can cover"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setResponseDialogOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSimulateResponse}
              disabled={processing || !responseCampaignId || !responsePhone || !responseMessage}
            >
              {processing ? "Processing..." : "Submit Response"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default ShiftFillingDashboard;
