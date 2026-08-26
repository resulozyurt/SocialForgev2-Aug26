// Types mirroring the SocialForge backend API responses.
// We'll extend this file as we build each phase screen.

export interface Brand {
  id: string;
  slug: string;
  display_name: string;
  industry: string | null;
  is_active: boolean;
  primary_color: string | null;
  secondary_color: string | null;
  accent_color: string | null;
  logo_url: string | null;
  voice_guide_url: string | null;
  monthly_post_target: number;
}

export interface BrandCreate {
  slug: string;
  display_name: string;
  industry?: string | null;
  monthly_post_target?: number;
}