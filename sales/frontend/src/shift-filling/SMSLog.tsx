import { useEffect, useState } from "react";
import { ShiftFillingNav } from "./ShiftFillingNav";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

type SMSMessage = {
  id: string;
  to: string;
  text: string;
  sent_at: string;
};

export const SMSLog = () => {
  const [messages, setMessages] = useState<SMSMessage[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchMessages = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/shift-filling/sms-log", {
        credentials: "include",
      });
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (error) {
      console.error("Error fetching SMS log:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMessages();
  }, []);

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleString();
    } catch {
      return dateStr;
    }
  };

  return (
    <div className="container mx-auto max-w-7xl py-6 px-4">
      <ShiftFillingNav />

      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">SMS Log</h1>
          <p className="text-muted-foreground text-sm">
            View sent SMS messages from shift filling outreach
          </p>
        </div>
        <Button onClick={fetchMessages} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Sent Messages</CardTitle>
          <CardDescription>
            {messages.length === 0
              ? "No messages sent yet"
              : `Showing ${messages.length} recent messages`}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="py-8 text-center">
              <div className="animate-spin text-2xl mb-2">⏳</div>
              <p className="text-muted-foreground">Loading messages...</p>
            </div>
          ) : messages.length === 0 ? (
            <div className="py-8 text-center">
              <div className="text-4xl mb-4">📭</div>
              <p className="text-muted-foreground">
                No SMS messages have been sent yet.
              </p>
              <p className="text-muted-foreground text-sm mt-2">
                Run a demo or process a calloff to see messages here.
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-40">Time</TableHead>
                  <TableHead className="w-32">To</TableHead>
                  <TableHead>Message</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {messages.map((msg) => (
                  <TableRow key={msg.id}>
                    <TableCell className="text-xs text-muted-foreground">
                      {formatDate(msg.sent_at)}
                    </TableCell>
                    <TableCell className="font-mono text-sm">{msg.to}</TableCell>
                    <TableCell className="max-w-md">
                      <p className="text-sm truncate" title={msg.text}>
                        {msg.text}
                      </p>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Card className="mt-6">
        <CardHeader>
          <CardTitle>About SMS Service</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground space-y-2">
          <p>
            <strong>Mock Mode:</strong> During POC testing, SMS messages are
            simulated and stored locally. No actual SMS messages are sent.
          </p>
          <p>
            <strong>Production Mode:</strong> When configured with RingCentral
            credentials, messages will be sent via the RingCentral SMS API.
          </p>
          <p>
            <strong>Webhook:</strong> In production, incoming SMS responses are
            received via webhook at{" "}
            <code className="bg-muted px-1 py-0.5 rounded">
              /api/shift-filling/webhook/sms
            </code>
          </p>
        </CardContent>
      </Card>
    </div>
  );
};

export default SMSLog;
