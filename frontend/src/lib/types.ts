// Types mirroring the SocialForge backend API responses.
// Extended in Phase C with the rich brand profile, solutions, competitors,
// and AI provider config shapes.

export type BrandLanguage = "en" | "tr";

export interface Brand {
  id: string;
  slug: string;
  display_name: string;
  industry: string | null;
  is_active: boolean;
  language: BrandLanguage;
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  logo_url: string | null;
  voice_guide_url: string | null;
  voice_guide_text: string | null;
  visual_identity: Record<string, unknown> | null;
  voice_profile: Record<string, unknown> | null;
  monthly_post_target: number;
}

export interface BrandCreate {
  slug: string;
  display_name: string;
  industry?: string | null;
  monthly_post_target?: number;
}

export type SolutionKey =
  | "merchandising"
  | "field_audit"
  | "field_sales"
  | "home_service"
  | "ai"
  | "general";

export interface BrandSolution {
  id: string;
  solution: SolutionKey;
  is_focus: boolean;
  priority: number;
  concept_notes: string | null;
  is_active: boolean;
}

export interface Competitor {
  id: string;
  name: string;
  is_aspirational: boolean;
  instagram_handle: string | null;
  linkedin_handle: string | null;
  x_handle: string | null;
}

export type PhaseKey = "phase1_research" | "phase2_calendar" | "phase3_copy";
export type ProviderKey = "anthropic" | "openai" | "google" | "groq";

export interface ProviderConfig {
  id: string;
  brand_id: string;
  phase: PhaseKey;
  provider: ProviderKey;
  model: string;
  api_key_masked: string;
  temperature: number;
  max_tokens: number;
  is_active: boolean;
}

export interface ProviderConfigCreate {
  phase: PhaseKey;
  provider: ProviderKey;
  model: string;
  api_key: string;
  temperature?: number;
  max_tokens?: number;
}

export interface ProviderTestResult {
  success: boolean;
  provider: string;
  model: string;
  latency_ms: number | null;
  error: string | null;
}
