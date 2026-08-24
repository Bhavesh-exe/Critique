const AGENTROUTER_BASE_URL = process.env.AGENTROUTER_BASE_URL || 'https://agentrouter.org/v1';
const AGENTROUTER_MODEL = process.env.AGENTROUTER_MODEL || 'gpt-5.6-sol';

interface GenerateContentOptions {
  systemInstruction?: string;
  temperature?: number;
  maxTokens?: number;
}

/**
 * Cleanly extracts JSON from an LLM response string, removing markdown fences or leading/trailing commentary if present.
 */
function extractJsonString(raw: string): string {
  const trimmed = raw.trim();
  // Match ```json ... ``` or ``` ... ```
  const codeBlockMatch = trimmed.match(/```(?:json)?\s*([\s\S]*?)\s*```/i);
  if (codeBlockMatch && codeBlockMatch[1]) {
    return codeBlockMatch[1].trim();
  }

  // Find outermost JSON object { ... } or array [ ... ]
  const firstBrace = trimmed.indexOf('{');
  const lastBrace = trimmed.lastIndexOf('}');
  if (firstBrace !== -1 && lastBrace > firstBrace) {
    return trimmed.substring(firstBrace, lastBrace + 1);
  }

  return trimmed;
}

export async function callAgentRouterAI(
  prompt: string,
  options: GenerateContentOptions = {}
): Promise<string> {
  const apiKey = (process.env.AGENTROUTER_API_KEY || process.env.OPENAI_API_KEY || '').trim();
  if (!apiKey) {
    throw new Error('AGENTROUTER_API_KEY is not configured in .env / .env.local.');
  }

  const model = AGENTROUTER_MODEL;
  const baseUrl = AGENTROUTER_BASE_URL.replace(/\/+$/, '');

  // Common headers required by AgentRouter WAF
  const clientHeaders = {
    'User-Agent': 'claude-cli/0.2.29 (external, cli)',
    'anthropic-version': '2023-06-01',
    'anthropic-beta': 'claude-code-20250219',
    'x-stainless-lang': 'js',
    'x-stainless-package-version': '0.2.29',
    'x-stainless-os': 'Windows',
    'x-stainless-arch': 'x64',
    'x-stainless-runtime': 'node',
  };

  // Primary attempt: Anthropic /v1/messages endpoint
  try {
    const messagesUrl = `${baseUrl}/messages`;
    const res = await fetch(messagesUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'x-api-key': apiKey,
        Authorization: `Bearer ${apiKey}`,
        ...clientHeaders,
      },
      body: JSON.stringify({
        model,
        max_tokens: options.maxTokens || 4096,
        temperature: options.temperature ?? 0.2,
        ...(options.systemInstruction ? { system: options.systemInstruction } : {}),
        messages: [{ role: 'user', content: prompt }],
      }),
    });

    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.content)) {
        const textBlock = data.content.find((c: { type: string; text?: string }) => c.type === 'text');
        if (textBlock?.text) return textBlock.text;
      }
      if (data?.choices?.[0]?.message?.content) {
        return data.choices[0].message.content;
      }
    } else {
      const errText = await res.text().catch(() => '');
      console.warn(`[AgentRouter /messages] returned status ${res.status}:`, errText);
    }
  } catch (err) {
    console.warn('[AgentRouter /messages] connection attempt failed:', err);
  }

  // Secondary fallback: OpenAI /v1/chat/completions endpoint
  const completionsUrl = `${baseUrl}/chat/completions`;
  const res = await fetch(completionsUrl, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${apiKey}`,
      ...clientHeaders,
    },
    body: JSON.stringify({
      model,
      messages: [
        ...(options.systemInstruction ? [{ role: 'system', content: options.systemInstruction }] : []),
        { role: 'user', content: prompt },
      ],
      temperature: options.temperature ?? 0.2,
      max_tokens: options.maxTokens || 4096,
    }),
  });

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    const message = errData?.error?.message || errData?.message || `HTTP ${res.status}: ${res.statusText}`;
    throw new Error(`AgentRouter API (${model}) failed: ${message}`);
  }

  const data = await res.json();
  const text = data?.choices?.[0]?.message?.content;
  if (typeof text !== 'string') {
    throw new Error('AgentRouter API returned an unexpected response structure.');
  }

  return text;
}

export const callAI = callAgentRouterAI;
export const callGemini = callAgentRouterAI; // Backwards compatibility

export interface FlowchartEvaluationResult {
  score: number;
  verdict: string;
  summary: string;
  issues: Array<{
    type: 'warning' | 'success' | 'info';
    msg: string;
  }>;
  missingComponents: string[];
  suggestedTechStack: string[];
  estimatedDifficulty: 'Beginner' | 'Intermediate' | 'Advanced' | 'Expert';
  estimatedTime: string;
}

export async function evaluateFlowchartWithAI(
  nodes: Array<{ id: string; label?: string; data?: { label?: string } }>,
  edges: Array<{ source: string; target: string; label?: string }>
): Promise<FlowchartEvaluationResult> {
  const nodeLabels = nodes.map((n) => n.label || n.data?.label || 'Unnamed Step');
  const connections = edges.map((e) => {
    const srcNode = nodes.find((n) => n.id === e.source);
    const dstNode = nodes.find((n) => n.id === e.target);
    const srcLabel = srcNode?.label || srcNode?.data?.label || e.source;
    const dstLabel = dstNode?.label || dstNode?.data?.label || e.target;
    return `${srcLabel} -> ${dstLabel}`;
  });

  const prompt = `You are a Principal Software Architect conducting an in-depth, rigorous architectural critique of a software system diagram.

Architecture Nodes (${nodes.length}):
${nodeLabels.map((l, i) => `${i + 1}. ${l}`).join('\n')}

Architecture Connections (${edges.length}):
${connections.length > 0 ? connections.join('\n') : 'No explicit connections defined.'}

Perform a deeply technical, hyper-critical evaluation covering:
1. Architectural completeness: Identify exact missing layers (e.g., missing API Gateway, no message broker for async tasks, lacking a caching layer like Redis, missing CDNs).
2. Reliability & Resilience: Point out single points of failure, missing dead-letter queues, lack of failovers or rate limiting.
3. Performance & Scalability: Identify synchronous bottlenecks, heavy database query loads without caching, and unscalable monolithic components.
4. Security & Isolation: Highlight missing Auth gateways, lack of VPC isolation, and data exposure risks.

Be brutal but constructive. Do not give generic advice. Give specific, concrete flaws based exactly on the nodes and connections provided. If it's a simple CRUD app, point out what it needs to reach enterprise scale.

Respond ONLY with a strictly valid JSON object matching this schema without any surrounding conversational text:
{
  "score": number (0 to 100 realistic score reflecting production readiness),
  "verdict": string (e.g. "Scalable & Resilient", "Solid Foundation with Auth Gaps", "High Single-Point-of-Failure Risk", "Missing Caching & Async Pipelines"),
  "summary": string (2-3 crisp, high-value sentences detailing the core strengths and critical structural gaps of this architecture),
  "issues": [
    {
      "type": "warning" | "success" | "info",
      "msg": string (concrete, high-impact critique explaining specifically why a component or missing connection is a flaw or strength)
    }
  ],
  "missingComponents": [string] (list of 3-5 specific missing production modules, e.g. "Redis Distributed Cache", "OAuth2 / JWT Gateway", "DLQ & Async Event Broker (Kafka/RabbitMQ)", "Prometheus / OpenTelemetry Monitoring"),
  "suggestedTechStack": [string] (list of 4-6 modern, battle-tested technologies and libraries best suited for this exact flow),
  "estimatedDifficulty": "Beginner" | "Intermediate" | "Advanced" | "Expert",
  "estimatedTime": string (e.g. "2-3 weeks", "1-2 months")
}`;

  try {
    const raw = await callAgentRouterAI(prompt, {
      systemInstruction:
        'You are an elite Principal Cloud Architect and Systems Designer. You provide sharp, realistic, high-value engineering reviews in strictly valid JSON format.',
      temperature: 0.2,
    });

    const cleanJson = extractJsonString(raw);
    const parsed = JSON.parse(cleanJson);

    return {
      score: typeof parsed.score === 'number' ? Math.min(100, Math.max(0, Math.round(parsed.score))) : 75,
      verdict: parsed.verdict || (parsed.score >= 80 ? 'Production Ready Architecture' : 'Architecture Needs Hardening'),
      summary: parsed.summary || 'Architecture analyzed successfully.',
      issues: Array.isArray(parsed.issues) ? parsed.issues : [],
      missingComponents: Array.isArray(parsed.missingComponents) ? parsed.missingComponents : [],
      suggestedTechStack: Array.isArray(parsed.suggestedTechStack) ? parsed.suggestedTechStack : [],
      estimatedDifficulty: parsed.estimatedDifficulty || 'Intermediate',
      estimatedTime: parsed.estimatedTime || '2-3 weeks',
    };
  } catch (err) {
    console.error('AgentRouter evaluateFlowchart error:', err);
    throw err; // Re-throw so API route handles it properly
  }
}

export interface GeneratedFlowchart {
  nodes: Array<{ id: string; label: string; x: number; y: number }>;
  edges: Array<{ id: string; source: string; target: string }>;
}

export async function generateFlowchartWithAI(
  projectPrompt: string,
  level: 'beginner' | 'intermediate' | 'advanced' = 'beginner'
): Promise<GeneratedFlowchart> {
  let systemRole = '';
  let levelInstructions = '';
  let exampleSchema = '';

  if (level === 'beginner') {
    systemRole = 'You are an expert Full-Stack Educator who creates crystal-clear, step-by-step End-to-End Data & HTTP Request lifecycle flowcharts in strictly valid JSON format.';
    levelInstructions = `Level: BEGINNER (Data Lifecycle & Request-Response Pipeline)
Focus: Make it completely obvious to a beginner how data moves from user interaction to backend and back to screen.

Flow Requirements (6 to 8 sequential steps):
1. Step 1 [UI & User Action]: User interaction in the frontend (e.g. form submission, click, search input in Next.js/React).
2. Step 2 [Client HTTP Request]: Frontend initiates an HTTP request (e.g. fetch('/api/...') with headers, auth tokens, and JSON payload).
3. Step 3 [API Route & Middleware]: Backend API handler receives the request, runs auth verification (Clerk/JWT), and parses the body.
4. Step 4 [External API / Core Logic]: Backend fetches external data or executes domain logic.
5. Step 5 [Data Persistence]: Backend saves/reads data in PostgreSQL using Prisma ORM.
6. Step 6 [HTTP JSON Response]: Server sends back formatted JSON response (status 200/201, payload, error handling).
7. Step 7 [Frontend State & Storage]: Client receives response, updates React state (Zustand / React Query / SWR).
8. Step 8 [UI Re-render & Display]: Component re-renders with fresh data, showing charts, tables, or success feedback to the user.

Layout: Linear vertical pipeline centered around x=280 with y-spacing of 120px per step (y=0, 120, 240, 360, 480, 600, 720, 840).`;

    exampleSchema = `{
  "nodes": [
    { "id": "1", "label": "1. User Action & Form Submit (React UI)", "x": 280, "y": 0 },
    { "id": "2", "label": "2. Client HTTP Request (fetch() + Auth Header)", "x": 280, "y": 120 },
    { "id": "3", "label": "3. Next.js API Route & Auth Middleware", "x": 280, "y": 240 },
    { "id": "4", "label": "4. External API Fetch & Processing", "x": 520, "y": 240 },
    { "id": "5", "label": "5. Database Persistence (PostgreSQL & Prisma)", "x": 280, "y": 360 },
    { "id": "6", "label": "6. Server HTTP Response (JSON 200 OK)", "x": 280, "y": 480 },
    { "id": "7", "label": "7. Client State Store (React Query / Zustand)", "x": 280, "y": 600 },
    { "id": "8", "label": "8. Dynamic UI Re-render & Visual Feedback", "x": 280, "y": 720 }
  ],
  "edges": [
    { "id": "e1-2", "source": "1", "target": "2" },
    { "id": "e2-3", "source": "2", "target": "3" },
    { "id": "e3-4", "source": "3", "target": "4" },
    { "id": "e4-5", "source": "4", "target": "5" },
    { "id": "e3-5", "source": "3", "target": "5" },
    { "id": "e5-6", "source": "5", "target": "6" },
    { "id": "e6-7", "source": "6", "target": "7" },
    { "id": "e7-8", "source": "7", "target": "8" }
  ]
}`;
  } else if (level === 'intermediate') {
    systemRole = 'You are a Senior Full-Stack Architect who designs clean, modular, and actionable software blueprints in strictly valid JSON format.';
    levelInstructions = `Level: INTERMEDIATE (Full-Stack Modular Architecture)
Focus: Break the project down into concrete, domain-specific architectural modules so an engineer can structure the full codebase.

Flow Requirements (7 to 9 structured modules):
1. Client UI Layer (Pages, Components & State Management)
2. API Gateway & Authentication Guards (Next.js Routes, Clerk Auth, Rate Limiting)
3. Domain Feature Services & Controllers (Core project business engines)
4. Distributed Cache & Session Store (Redis)
5. Relational Database & Models (PostgreSQL & Prisma ORM Schema)
6. Third-Party Integrations / External APIs (Payments, Market Feeds, Webhooks)
7. Background Queue & Async Workers (Cron / BullMQ Task Runners)

Layout: 3-channel layout (Center Spine x=300 for UI/API/Controllers, Left Wing x=40 for Cache/Workers, Right Wing x=560 for DB/External APIs). Y spaced by 130px.`;

    exampleSchema = `{
  "nodes": [
    { "id": "1", "label": "Client UI & View Layer (Next.js & Tailwind)", "x": 300, "y": 0 },
    { "id": "2", "label": "API Route Handlers & Auth Guard (Clerk)", "x": 300, "y": 130 },
    { "id": "3", "label": "Core Feature Logic & Controller Service", "x": 300, "y": 260 },
    { "id": "4", "label": "In-Memory Cache (Redis)", "x": 40, "y": 260 },
    { "id": "5", "label": "PostgreSQL Database (Prisma ORM)", "x": 560, "y": 260 },
    { "id": "6", "label": "External Third-Party API Provider", "x": 560, "y": 390 },
    { "id": "7", "label": "Async Background Task Worker (BullMQ)", "x": 300, "y": 520 }
  ],
  "edges": [
    { "id": "e1-2", "source": "1", "target": "2" },
    { "id": "e2-3", "source": "2", "target": "3" },
    { "id": "e3-4", "source": "3", "target": "4" },
    { "id": "e3-5", "source": "3", "target": "5" },
    { "id": "e3-6", "source": "3", "target": "6" },
    { "id": "e7-5", "source": "7", "target": "5" }
  ]
}`;
  } else {
    // Advanced
    systemRole = 'You are a Principal Cloud Architect who designs highly scalable, resilient, distributed cloud infrastructures in strictly valid JSON format.';
    levelInstructions = `Level: ADVANCED (Production Distributed Cloud Architecture)
Focus: Design an enterprise-grade, highly available distributed system with load balancing, microservices, caching, event streaming, and DB replication.

Flow Requirements (8 to 11 production components):
1. Edge CDN & WAF (Cloudflare / AWS CloudFront)
2. Client SSR Pods (Next.js Container Cluster)
3. API Gateway & Envoy Load Balancer (JWT Auth, Rate Limiter, Reverse Proxy)
4. Decoupled Domain Microservices (Core feature services)
5. Redis Distributed Cluster & Multi-Region Caching
6. Event Streaming Broker (Apache Kafka / RabbitMQ / SQS)
7. Primary Database (PostgreSQL Master with PgBouncer Pooling)
8. Read-Replica Database Cluster (TimescaleDB / Postgres Read Replicas)
9. Background Worker Pool (Distributed Consumers & ETL Pipelines)
10. Third-Party Webhooks & External Gateways

Layout: Clean multi-tier production hierarchy with strict non-crossing connections.`;

    exampleSchema = `{
  "nodes": [
    { "id": "1", "label": "Edge CDN & Global WAF (Cloudflare)", "x": 300, "y": 0 },
    { "id": "2", "label": "Next.js SSR Frontend Cluster", "x": 300, "y": 120 },
    { "id": "3", "label": "API Gateway & Envoy Load Balancer", "x": 300, "y": 240 },
    { "id": "4", "label": "Core Domain Microservices", "x": 300, "y": 360 },
    { "id": "5", "label": "Redis Distributed Cache Cluster", "x": 40, "y": 360 },
    { "id": "6", "label": "Event Message Broker (Kafka / BullMQ)", "x": 40, "y": 480 },
    { "id": "7", "label": "Primary PostgreSQL Master (Write DB)", "x": 560, "y": 360 },
    { "id": "8", "label": "Read-Replica DB Cluster (Read Queries)", "x": 560, "y": 480 },
    { "id": "9", "label": "Distributed Worker Fleet", "x": 40, "y": 600 },
    { "id": "10", "label": "Third-Party External Services", "x": 560, "y": 600 }
  ],
  "edges": [
    { "id": "e1-2", "source": "1", "target": "2" },
    { "id": "e2-3", "source": "2", "target": "3" },
    { "id": "e3-4", "source": "3", "target": "4" },
    { "id": "e4-5", "source": "4", "target": "5" },
    { "id": "e4-7", "source": "4", "target": "7" },
    { "id": "e4-6", "source": "4", "target": "6" },
    { "id": "e6-9", "source": "6", "target": "9" },
    { "id": "e9-7", "source": "9", "target": "7" },
    { "id": "e4-8", "source": "4", "target": "8" },
    { "id": "e4-10", "source": "4", "target": "10" }
  ]
}`;
  }

  const prompt = `Convert the following project description into a structured visual flowchart diagram.

Project Context:
"${projectPrompt}"

${levelInstructions}

General Rules:
- Return ONLY a strictly valid JSON object matching the schema below.
- Do NOT include markdown commentary or extra keys.
- Nodes must have short, informative labels with technology in parentheses.
- Connections must be clean without unnecessary crossings.

Schema Example:
${exampleSchema}`;

  try {
    const raw = await callAgentRouterAI(prompt, {
      systemInstruction: systemRole,
      temperature: 0.1,
    });

    const cleanJson = extractJsonString(raw);
    const parsed = JSON.parse(cleanJson);

    if (Array.isArray(parsed.nodes) && parsed.nodes.length > 0) {
      return {
        nodes: parsed.nodes.map((n: { id?: string; label?: string; x?: number; y?: number }, idx: number) => ({
          id: String(n.id || idx + 1),
          label: n.label || `Step ${idx + 1}`,
          x: typeof n.x === 'number' ? n.x : 280,
          y: typeof n.y === 'number' ? n.y : idx * 120,
        })),
        edges: Array.isArray(parsed.edges)
          ? parsed.edges.map((e: { id?: string; source?: string; target?: string }, idx: number) => ({
              id: e.id || `e-${idx}`,
              source: String(e.source),
              target: String(e.target),
            }))
          : [],
      };
    }
    throw new Error('Invalid flowchart node structure received from AI.');
  } catch (err) {
    console.error('AgentRouter generateFlowchart error:', err);
    throw err;
  }
}
