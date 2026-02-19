export interface ServerEvent {
  event_id: string;
  session_id: string;
  type:
    | "client.transcript_segment"
    | "client.transcript_final"
    | "server.transcript_final"
    | "client.resume"
    | "server.ack"
    | "server.rule_alert"
    | "server.guidance_update"
    | "server.required_question_status"
    | "system.ping"
    | "system.pong"
    | "system.resync";
  ts_created: string;
  schema_version: string;
  payload: Record<string, unknown>;
  client_seq?: number | null;
  server_seq?: number | null;
}

export class SessionWebSocket {
  private ws: WebSocket | null = null;
  private clientSeq = 0;
  private lastServerSeq = 0;
  private reconnectAttempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;

  constructor(
    private sessionId: string,
    private onEvent: (event: ServerEvent) => void,
    private onError: (error: string) => void
  ) {}

  connect(): void {
    this.intentionalClose = false;
    this.openSocket();
  }

  private openSocket(): void {
    const wsUrl = `${process.env.NEXT_PUBLIC_WS_URL}/ws/session/${this.sessionId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.reconnectAttempt = 0;
      this.sendResume();
    };

    this.ws.onmessage = (msg) => {
      try {
        const event: ServerEvent = JSON.parse(msg.data);

        if (event.type === "system.ping") {
          this.sendPong();
          return;
        }

        if (event.server_seq && event.server_seq <= this.lastServerSeq) {
          return;
        }
        if (event.server_seq) {
          this.lastServerSeq = event.server_seq;
        }
        this.onEvent(event);
      } catch {
        this.onError("Failed to parse WebSocket message");
      }
    };

    this.ws.onerror = () => this.onError("WebSocket error");
    this.ws.onclose = () => {
      if (this.intentionalClose) {
        return;
      }
      this.onError("WebSocket closed");
      this.scheduleReconnect();
    };
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) {
      return;
    }
    const delayMs = Math.min(1000 * 2 ** this.reconnectAttempt, 30000);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.reconnectAttempt += 1;
      this.openSocket();
    }, delayMs);
  }

  private sendResume(): void {
    this.clientSeq += 1;
    this.sendRaw({
      event_id: crypto.randomUUID(),
      session_id: this.sessionId,
      type: "client.resume",
      ts_created: new Date().toISOString(),
      schema_version: "1.0",
      payload: { last_server_seq: this.lastServerSeq },
      client_seq: this.clientSeq,
      server_seq: null,
    });
  }

  private sendPong(): void {
    this.clientSeq += 1;
    this.sendRaw({
      event_id: crypto.randomUUID(),
      session_id: this.sessionId,
      type: "system.pong",
      ts_created: new Date().toISOString(),
      schema_version: "1.0",
      payload: {},
      client_seq: this.clientSeq,
      server_seq: null,
    });
  }

  private sendRaw(event: Record<string, unknown>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      return;
    }
    this.ws.send(JSON.stringify(event));
  }

  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close();
  }
}
