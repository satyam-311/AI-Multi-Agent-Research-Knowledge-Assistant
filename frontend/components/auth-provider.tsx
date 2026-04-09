"use client";

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode
} from "react";
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  signInWithEmailAndPassword,
  signInWithPopup,
  signOut,
  type User,
  type UserCredential
} from "firebase/auth";
import { auth, provider } from "@/lib/firebase";
import {
  clearAuthSession,
  loginWithGoogle,
  logout as logoutRequest,
  setAuthSession,
  type AuthSession,
  type AuthUser
} from "@/lib/api";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<void>;
  signInWithGoogle: () => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

type FirebaseErrorLike = Error & { code?: string };

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function normalizeEmail(email: string) {
  return email.trim().toLowerCase();
}

function formatAuthError(error: unknown) {
  const authError = error as FirebaseErrorLike;
  const code = authError?.code ?? "";

  if (!authError || !(authError instanceof Error)) {
    return "Google sign-in failed.";
  }

  if (code === "auth/invalid-email" || authError.message.includes("auth/invalid-email")) {
    return "Enter a valid email address.";
  }

  if (
    code === "auth/missing-password" ||
    code === "auth/invalid-credential" ||
    code === "auth/wrong-password" ||
    authError.message.includes("auth/wrong-password")
  ) {
    return "Incorrect email or password.";
  }

  if (code === "auth/user-not-found" || authError.message.includes("auth/user-not-found")) {
    return "No account was found for that email.";
  }

  if (code === "auth/email-already-in-use") {
    return "An account with this email already exists.";
  }

  if (code === "auth/weak-password") {
    return "Use a stronger password with at least 6 characters.";
  }

  if (code === "auth/too-many-requests") {
    return "Too many sign-in attempts. Please wait a moment and try again.";
  }

  if (authError.message.includes("auth/configuration-not-found")) {
    return "Google sign-in is not configured in Firebase for this project. Enable Google under Authentication > Sign-in method and add localhost to Authorized domains.";
  }

  if (authError.message.includes("auth/popup-closed-by-user")) {
    return "The Google sign-in popup was closed before authentication completed.";
  }

  if (authError.message.includes("auth/popup-blocked")) {
    return "The browser blocked the Google sign-in popup. Allow popups for this site and try again.";
  }

  if (
    authError.message.includes("FIREBASE_SERVICE_ACCOUNT_KEY_PATH") ||
    authError.message.includes("FIREBASE_SERVICE_ACCOUNT_JSON")
  ) {
    return "The backend is missing Firebase Admin credentials. Configure FIREBASE_SERVICE_ACCOUNT_JSON, FIREBASE_SERVICE_ACCOUNT_KEY_PATH, or the FIREBASE_CLIENT_EMAIL and FIREBASE_PRIVATE_KEY env vars, then restart the backend.";
  }

  return authError.message;
}

function mergeUser(firebaseUser: User | null, session: AuthSession | null): AuthUser | null {
  if (!firebaseUser || !session) {
    return null;
  }

  return {
    ...session.user,
    name: firebaseUser.displayName || session.user.name,
    email: firebaseUser.email || session.user.email,
    photo_url: firebaseUser.photoURL,
    provider: firebaseUser.providerData[0]?.providerId ?? "google.com"
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const restoringRef = useRef(false);

  const syncFirebaseUser = async (firebaseUser: User) => {
    const idToken = await firebaseUser.getIdToken(true);
    console.log("Firebase ID Token:", idToken);

    const response = await loginWithGoogle(idToken);
    const session = {
      token: response.token,
      user: {
        ...response.user,
        photo_url: firebaseUser.photoURL,
        provider: firebaseUser.providerData[0]?.providerId ?? "google.com"
      }
    };

    setAuthSession(session);
    setUser(mergeUser(firebaseUser, session));
    setError(null);
  };

  const resetLocalAuthState = () => {
    clearAuthSession();
    setUser(null);
  };

  const handleAuthFailure = async (authError: unknown) => {
    if (authError instanceof Error && authError.message.includes("Invalid Google sign-in token")) {
      await signOut(auth).catch(() => undefined);
    }
    resetLocalAuthState();
    setError(formatAuthError(authError));
  };

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (!firebaseUser) {
        resetLocalAuthState();
        setLoading(false);
        return;
      }

      if (restoringRef.current) {
        return;
      }

      setLoading(true);
      try {
        await syncFirebaseUser(firebaseUser);
      } catch (authError) {
        await handleAuthFailure(authError);
      } finally {
        restoringRef.current = false;
        setLoading(false);
      }
    });

    return unsubscribe;
  }, []);

  const completeCredentialSignIn = async (credentialPromise: Promise<UserCredential>) => {
    setLoading(true);
    setError(null);
    restoringRef.current = true;

    try {
      const result = await credentialPromise;
      await syncFirebaseUser(result.user);
    } catch (authError) {
      await handleAuthFailure(authError);
      throw authError;
    } finally {
      restoringRef.current = false;
      setLoading(false);
    }
  };

  const handleGoogleSignIn = async () => {
    await completeCredentialSignIn(signInWithPopup(auth, provider));
  };

  const handleEmailSignIn = async (email: string, password: string) => {
    const normalizedEmail = normalizeEmail(email);
    if (!EMAIL_PATTERN.test(normalizedEmail)) {
      const error = new Error("Enter a valid email address.");
      setError(error.message);
      throw error;
    }
    await completeCredentialSignIn(signInWithEmailAndPassword(auth, normalizedEmail, password));
  };

  const handleEmailSignUp = async (email: string, password: string) => {
    const normalizedEmail = normalizeEmail(email);
    if (!EMAIL_PATTERN.test(normalizedEmail)) {
      const error = new Error("Enter a valid email address.");
      setError(error.message);
      throw error;
    }
    await completeCredentialSignIn(
      createUserWithEmailAndPassword(auth, normalizedEmail, password)
    );
  };

  const handleLogout = async () => {
    setLoading(true);
    setError(null);

    try {
      await signOut(auth);
      await logoutRequest().catch(() => undefined);
    } finally {
      clearAuthSession();
      setUser(null);
      setLoading(false);
    }
  };

  const value = useMemo(
    () => ({
      user,
      loading,
      error,
      signInWithEmail: handleEmailSignIn,
      signUpWithEmail: handleEmailSignUp,
      signInWithGoogle: handleGoogleSignIn,
      logout: handleLogout
    }),
    [error, loading, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider.");
  }
  return context;
}
