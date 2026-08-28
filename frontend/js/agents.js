/**
 * RP360 // Multi-Agent Definitions & Configurations
 * Encapsulates metadata, endpoint mappings, placeholders, and default prompt templates for all 5 backend agents.
 */

export const AGENTS = {
  regulatory: {
    id: "regulatory",
    name: "FDA Regulatory Navigator",
    badge: "STATEFUL &middot; HITL",
    icon: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>`,
    description: "Evaluates medical device specifications, 510(k)/PMA pathways, predicate data, and Human-in-the-Loop review checkpoints with PostgreSQL memory.",
    color: "var(--brand)",
    endpoint: "/interact",
    wsEndpoint: "/ws/interact",
    supportsHITL: true,
    supportsWs: true,
    inputPlaceholder: "Ask about FDA 510(k)/PMA pathways, device classification, or predicate devices...",
    defaultPrompt: "What FDA testing standards and 510(k) predicate validation data are required for a clinical pulse oximeter?",
    params: {
      device_class: "Class II (510k Premarket Notification)",
      intended_use: "Continuous pulse oximetry monitoring for clinical ICU patients",
      predicate_device: "",
      is_samd: true,
      use_device_data: false,
      device_specs: "",
    },
    suggestions: [
      {
        title: "FDA 510(k) Pulse Oximeter Criteria",
        desc: "Analyze testing standards & predicate requirements for ICU oximetry.",
        prompt: "What FDA testing standards and 510(k) predicate validation data are required for a clinical pulse oximeter?"
      },
      {
        title: "SaMD Cybersecurity Premarket Guidance",
        desc: "Review 2023 FDA cybersecurity documentation requirements.",
        prompt: "What cybersecurity and FDA 2023 premarket guidance documentation is needed for Software as a Medical Device (SaMD)?"
      },
      {
        title: "ISO 10993 Biocompatibility Testing",
        desc: "Evaluate patient-contacting sensor probe biocompatibility.",
        prompt: "Analyze biocompatibility testing under ISO 10993 for patient-contacting pulse oximeter probes."
      },
      {
        title: "21 CFR 870.2700 Pathway Analysis",
        desc: "Examine clinical performance validation benchmarks.",
        prompt: "Evaluate clinical performance validation requirements under 21 CFR 870.2700."
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
    inputPlaceholder: "Enter deep research topic (e.g. Surgical robotic stapler safety recalls & MAUDE trends)...",
    defaultPrompt: "Recent FDA safety communications and recall trends on surgical robotic staplers.",
    params: {},
    suggestions: [
      {
        title: "Robotic Stapler Safety Recalls",
        desc: "Investigate FDA safety communications & recall patterns.",
        prompt: "Recent FDA safety communications and recall trends on surgical robotic staplers."
      },
      {
        title: "AI/ML Diagnostic 510(k) Trends",
        desc: "Examine premarket clearance trends for medical AI models.",
        prompt: "AI/ML diagnostic medical software 510(k) premarket clearance requirements 2024-2026."
      },
      {
        title: "EU MDR vs US FDA PMS Obligations",
        desc: "Compare post-market surveillance & clinical evaluation.",
        prompt: "EU MDR vs US FDA Post-Market Surveillance (PMS) reporting obligations."
      },
      {
        title: "ISO 13485 CAPA Warning Letters",
        desc: "Audit common 483 inspection findings in quality systems.",
        prompt: "FDA warning letters and 483 observations related to ISO 13485 CAPA systems."
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
    activeMode: localStorage.getItem("rp360_mcp_mode") || "harry_potter",
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
    inputPlaceholder: "Ask a database question (e.g. Show all Class II medical devices approved after 2020)...",
    defaultPrompt: "Show all medical devices registered under Class II",
    params: {},
    suggestions: [
      {
        title: "Class II Medical Devices",
        desc: "Query all registered Class II devices in database.",
        prompt: "Show all medical devices registered under Class II"
      },
      {
        title: "Approved Device Counts by Class",
        desc: "Aggregate statistics across classification tiers.",
        prompt: "Count the number of approved medical devices by risk class"
      },
      {
        title: "Top Approved Devices Post-2020",
        desc: "Filter recent high-risk device clearances.",
        prompt: "List top 5 devices approved after 2020 with high risk classification"
      },
      {
        title: "Predicate Reference Statistics",
        desc: "Analyze predicate references and recall correlations.",
        prompt: "Show device recall statistics and predicate references"
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
    defaultPrompt: "My company is developing a pulse oximeter for clinical use. What class is this?",
    params: {},
    suggestions: [
      {
        title: "Pulse Oximeter Classification",
        desc: "Determine risk tier & general requirements.",
        prompt: "My company is developing a pulse oximeter for clinical use. What class is this?"
      },
      {
        title: "Test Multi-Turn Memory",
        desc: "Recall context from previous dialogue turns.",
        prompt: "What device did I mention previously in our conversation?"
      },
      {
        title: "510(k) Substantial Equivalence",
        desc: "Understand technological characteristics comparison.",
        prompt: "Explain 510(k) Substantial Equivalence criteria."
      },
      {
        title: "ISO 14971 Risk Management",
        desc: "Review essential risk management lifecycle steps.",
        prompt: "What are the essential requirements of ISO 14971 risk management?"
      }
    ]
  }
};
