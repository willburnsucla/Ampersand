/**
 * Sign-in route — PLACEHOLDER.
 * The real sign-in/create-account form is the frontend team's to build.
 * The auth plumbing is done! Next -> build a form with email + password inputs and call the documented helpers from '@/lib/auth-client':
 *   const signIn = useSignIn()  
 *   const signUp = useSignUp() 
 * On success the session cookie is set automatically and the user can be sent
 */
export default function SignInPage() {
  return (
    <main className="flex h-screen items-center justify-center">
      <div className="text-center text-muted-foreground">
        <h1 className="text-lg font-medium">Sign-in UI — TODO (frontend team)</h1>
        <p className="mt-2 text-sm">
          Auth is wired. Build the form here and call useSignIn() / useSignUp()
          from lib/auth-client. See AUTH.md.
        </p>
      </div>
    </main>
  )
}
