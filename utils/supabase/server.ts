import { createServerClient } from "@supabase/ssr";

type CookieItem = {
  name: string;
  value: string;
  options?: Record<string, unknown>;
};

type CookieAdapter = {
  getAll: () => CookieItem[];
  setAll?: (cookiesToSet: CookieItem[]) => void;
};

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_DEFAULT_KEY;

export const createClient = (cookieAdapter: CookieAdapter) => {
  return createServerClient(supabaseUrl!, supabaseKey!, {
    cookies: {
      getAll() {
        return cookieAdapter.getAll();
      },
      setAll(cookiesToSet) {
        cookieAdapter.setAll?.(cookiesToSet);
      },
    },
  });
};
