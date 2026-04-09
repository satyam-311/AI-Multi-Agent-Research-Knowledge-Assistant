declare module "@/lib/firebase" {
  import type { Auth, GoogleAuthProvider } from "firebase/auth";

  export const auth: Auth;
  export const provider: GoogleAuthProvider;
}
