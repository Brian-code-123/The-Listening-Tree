// In the original app the chat page is served at "/" (GET / renders
// chat.html), and links across the app — "Normal Mode" on /accessibility,
// the post-login redirect — point at "/" for it. So the root renders the
// chat page itself rather than redirecting somewhere else; /chat stays
// available as an explicit alias for the same screen.
export { default } from "./chat/page";
