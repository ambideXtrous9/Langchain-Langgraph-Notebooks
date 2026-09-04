/**
 * AgentSphere // Multi-Agent Definitions & Configurations
 * Encapsulates metadata, endpoint mappings, placeholders, and default prompt templates for all 5 backend agents.
 */

export const AGENTS = {
  policy: {
    id: "policy",
    name: "Policy & Standards Navigator",
    badge: "SYSTEM AUDIT &middot; HITL",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    description: "Evaluates system architecture specifications, policy compliance standards, benchmark data, and Human-in-the-Loop review checkpoints with PostgreSQL memory.",
    color: "var(--brand)",
    endpoint: "/interact",
    wsEndpoint: "/ws/interact",
    supportsHITL: true,
    supportsWs: true,
    hasParams: true,
    inputPlaceholder: "Ask about policy compliance tiers, system architecture standards, or benchmark references...",
    defaultPrompt: "What security controls and reference validation benchmarks are required for an enterprise data pipeline?",
    params: {
      system_tier: "Tier 2 (Advanced Verification Standards)",
      intended_use: "Continuous cloud telemetry monitoring and identity verification",
      reference_standard: "",
      is_autonomous: true,
      use_system_data: false,
      system_specs: "",
    },
    suggestions: [
      {
        title: "Tier 2 Verification Criteria",
        desc: "Analyze security controls & benchmark validation for telemetry pipelines.",
        prompt: "What security controls and reference validation benchmarks are required for an enterprise data pipeline?"
      },
      {
        title: "Autonomous AI Cloud Guidance",
        desc: "Review enterprise AI pre-deployment verification requirements.",
        prompt: "What governance and pre-deployment verification documentation is needed for Autonomous Cloud Systems?"
      },
      {
        title: "ISO 27001 Security Controls",
        desc: "Evaluate distributed cluster telemetry security.",
        prompt: "Analyze security verification controls under ISO/IEC 27001 for distributed systems."
      },
      {
        title: "NIST 800-53 Baseline Audit",
        desc: "Examine system performance validation benchmarks.",
        prompt: "Evaluate audit compliance validation requirements under NIST SP 800-53."
      }
    ]
  },

  research: {
    id: "research",
    name: "Autonomous Deep Research",
    badge: "PARALLEL &middot; defer=true",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/><line x1="11" y1="8" x2="11" y2="14"/><line x1="8" y1="11" x2="14" y2="11"/></svg>`,
    description: "Parallel multi-critic deep research engine with autonomous Planner, live DuckDuckGo web search, Fact & Style Critics, and synchronized Publisher join.",
    color: "#a04000",
    endpoint: "/research/stream",
    syncEndpoint: "/research/run",
    supportsHITL: false,
    inputPlaceholder: "Enter deep research topic (e.g. Distributed cloud consensus protocols & security advisories)...",
    defaultPrompt: "Recent security advisories and resilience trends in cloud container orchestration.",
    params: {},
    suggestions: [
      {
        title: "Cloud Container Resilience",
        desc: "Investigate security advisories & resilience patterns.",
        prompt: "Recent security advisories and resilience trends in cloud container orchestration."
      },
      {
        title: "Autonomous AI Governance",
        desc: "Examine validation frameworks for enterprise models.",
        prompt: "Enterprise AI governance standards and validation requirements 2024-2026."
      },
      {
        title: "SOC 2 vs ISO 27001 Audits",
        desc: "Compare continuous audit & compliance monitoring.",
        prompt: "SOC 2 Type II vs ISO 27001 continuous audit and monitoring obligations."
      },
      {
        title: "Zero Trust Architecture Patterns",
        desc: "Audit implementation standards under NIST SP 800-207.",
        prompt: "Zero Trust architecture guidelines and network access implementation patterns."
      }
    ]
  },

  mcp: {
    id: "mcp",
    name: "MCP Multi-Agent Intelligence",
    badge: "MCP &middot; Dual Engine",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/></svg>`,
    description: "Multi-Server Model Context Protocol (MCP) manager. Toggle between Harry Potter Universe Question Answering (Pinecone MCP) and Airbnb Travel Search (OpenBNB MCP + Weather).",
    color: "#117864",
    endpoint: "/mcp/stream",
    syncEndpoint: "/mcp/run",
    supportsHITL: false,
    activeMode: localStorage.getItem("agentsphere_mcp_mode") || "harry_potter",
    modes: {
      harry_potter: {
        id: "harry_potter",
        label: "⚡ Harry Potter QA",
        badge: "Multi-Hop Pinecone MCP · hpvdb-openai",
        description: "Multi-Hop Reasoning agent querying the Pinecone vector database across the 7-book corpus using the full Pinecone MCP tool suite (search-records, describe-index-stats, rerank-documents, cascading-search).",
        inputPlaceholder: "Ask anything about the Harry Potter universe (e.g. Explain the allegiance history of the Elder Wand)...",
        defaultPrompt: "Explain the history of the Elder Wand and how its allegiance transferred across the series based on the books",
        pills: [
          "Multi-Hop Reasoning (3-Hops)",
          "@pinecone-database/mcp (hpvdb-openai)",
          "Vector Reranking",
          "HP Lore Scholar"
        ],
        suggestions: [
          {
            title: "Elder Wand Allegiance",
            desc: "Explore wandlore rules and how ownership passed from Dumbledore to Harry.",
            prompt: "Explain the history of the Elder Wand and how its allegiance transferred across the series based on the books"
          },
          {
            title: "The Triwizard Third Task",
            desc: "Retrieve book details on the maze creatures, sphinx riddle, and portkey cup.",
            prompt: "What happened during the third task of the Triwizard Tournament in the maze in Goblet of Fire?"
          },
          {
            title: "Voldemort's 7 Horcruxes",
            desc: "Chronicle every Horcrux, its vessel, history, location, and destruction.",
            prompt: "List all 7 Horcruxes created by Voldemort, their historical significance, and how each was destroyed"
          },
          {
            title: "Secret of the Marauder's Map",
            desc: "How Moony, Wormtail, Padfoot, and Prongs created the enchanted map.",
            prompt: "Explain the creation of the Marauder's Map and how Remus Lupin and Sirius Black used it at Hogwarts"
          }
        ]
      },
      airbnb: {
        id: "airbnb",
        label: "🏨 Airbnb Search",
        badge: "Airbnb MCP · OpenBNB",
        description: "Subprocess MCP agent searching live Airbnb properties, cottages, and villas synthesized with 3-day weather forecasts.",
        inputPlaceholder: "Search accommodations & destination (e.g. Find top 3 cottages in Darjeeling with mountain view)...",
        defaultPrompt: "Find top 3 cottages in Darjeeling for 2 people with mountain view",
        pills: [
          "@openbnb/mcp-server-airbnb (stdio)",
          "WeatherAPI ReAct",
          "Live Geocoding"
        ],
        suggestions: [
          {
            title: "Darjeeling Mountain Cottages",
            desc: "Find top 3 stays for 2 guests with mountain views & weather.",
            prompt: "Find top 3 cottages in Darjeeling for 2 people with mountain view"
          },
          {
            title: "Goa Beachfront Villa",
            desc: "Weekend stay for 4 adults with pool & weather outlook.",
            prompt: "Weekend beach villa in North Goa for 4 guests with pool"
          },
          {
            title: "Manali Valley Chalet",
            desc: "Cozy stay near Solang Valley with heating & climate advisories.",
            prompt: "Cozy chalet in Manali near Solang Valley for 2 adults"
          },
          {
            title: "Kyoto Traditional Apartment",
            desc: "Quiet stay near Gion with weather summary.",
            prompt: "Quiet apartment in Kyoto near Gion for 2 travelers"
          }
        ]
      }
    },
    get currentModeConfig() {
      return this.modes[this.activeMode] || this.modes.harry_potter;
    },
    get suggestions() {
      return this.currentModeConfig.suggestions;
    },
    get inputPlaceholder() {
      return this.currentModeConfig.inputPlaceholder;
    },
    get defaultPrompt() {
      return this.currentModeConfig.defaultPrompt;
    }
  },

  sql: {
    id: "sql",
    name: "Text-to-SQL Analyst",
    badge: "SQL DATABASE",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/></svg>`,
    description: "Translates natural language questions into executable SQL, runs against PostgreSQL database, and formats interactive tabular grids.",
    color: "#1b4f72",
    endpoint: "/get_sql_query",
    supportsHITL: false,
    inputPlaceholder: "Ask a database question (e.g. Show all Tier 2 enterprise systems certified after 2020)...",
    defaultPrompt: "Show all enterprise systems registered under Tier 2",
    params: {},
    suggestions: [
      {
        title: "Tier 2 Enterprise Systems",
        desc: "Query all registered Tier 2 systems in database.",
        prompt: "Show all enterprise systems registered under Tier 2"
      },
      {
        title: "Certified System Counts by Tier",
        desc: "Aggregate statistics across classification tiers.",
        prompt: "Count the number of certified systems by risk tier"
      },
      {
        title: "Top Systems Certified Post-2020",
        desc: "Filter recent high-risk system clearances.",
        prompt: "List top 5 systems certified after 2020 with high risk classification"
      },
      {
        title: "Vendor Benchmark Statistics",
        desc: "Analyze system benchmarks and vendor correlations.",
        prompt: "Show system audit statistics and vendor reference benchmarks"
      }
    ]
  },

  chat: {
    id: "chat",
    name: "General Assistant (Postgres Memory)",
    badge: "POSTGRES MEMORY",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>`,
    description: "Conversational dialogue agent with multi-turn memory persisted in PostgreSQL PostgresChatMessageHistory with session management.",
    color: "var(--brand-ink)",
    endpoint: "/generic_chat",
    supportsHITL: false,
    inputPlaceholder: "Ask a question or continue the conversation (PostgreSQL memory active)...",
    defaultPrompt: "My organization is deploying a distributed data ingestion pipeline. What architecture tier is this?",
    params: {},
    suggestions: [
      {
        title: "System Tier Classification",
        desc: "Determine risk tier & general requirements.",
        prompt: "My organization is deploying a distributed data ingestion pipeline. What architecture tier is this?"
      },
      {
        title: "Test Multi-Turn Memory",
        desc: "Recall context from previous dialogue turns.",
        prompt: "What system did I mention previously in our conversation?"
      },
      {
        title: "Security Baseline Equivalence",
        desc: "Understand technological characteristics comparison.",
        prompt: "Explain technical characteristics and security baseline verification."
      },
      {
        title: "ISO 27001 Risk Management",
        desc: "Review essential risk management lifecycle steps.",
        prompt: "What are the essential requirements of ISO 27001 risk assessment?"
      }
    ]
  },

  stock: {
    id: "stock",
    name: "NSE Stock Analysis (Swarm)",
    badge: "NIFTY 500 &middot; 13 LENSES &middot; PINECONE MCP",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
    description: "Institutional multi-agent stock analysis with embedded DuckDB fact store, Pinecone MCP vector search, Yahoo Finance real-time market data, GNews market sentiment, 13 analyst lenses, 4-tier verification audit, and HTML publication report assembly.",
    color: "#2563eb",
    endpoint: "/stock/analyze",
    reportEndpoint: (runId) => `/stock/report/${runId}`,
    mermaidEndpoint: "/stock/mermaid",
    supportsHITL: false,
    hasParams: true,
    inputPlaceholder: "Ask in plain English (e.g. 'compare HDFC Bank and Reliance performance for next 6 months' or 'research on HDFC Bank in depth')...",
    defaultPrompt: "compare HDFC Bank and Reliance performance for next 6 months",
    params: {
      sector_filter: "",
      max_lenses: 6,
    },
    suggestions: [
      {
        title: "HDFC Bank vs Reliance 6M Comparison",
        desc: "Master Planner: DuckDB metrics, Yahoo Finance 6M history, GNews, & Monte Carlo simulations.",
        prompt: "compare HDFC Bank and Reliance performance for next 6 months"
      },
      {
        title: "In-Depth Research on HDFC Bank",
        desc: "Master Planner: CSV, DuckDB fact store, Yahoo Finance targets, news narratives, and risk audit.",
        prompt: "research on HDFC Bank in depth"
      },
      {
        title: "Tata Motors vs M&M 1-Year Horizon",
        desc: "Automotive peer comparison across valuations, ROE, debt, and Markowitz portfolio weights.",
        prompt: "compare Tata Motors and Mahindra & Mahindra performance for next 1 year"
      },
      {
        title: "Financial Services Sector Screen",
        desc: "Screen Financial Services for high ROE, healthy P/B, and institutional conviction.",
        prompt: "Screen Financial Services stocks with ROE > 15%, robust price-to-book, and favorable valuation"
      }
    ]
  }
};
