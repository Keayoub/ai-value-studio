import http from "node:http";

type AuthorizationCodeListener = {
  redirectUri: string;
  waitForCode: () => Promise<string>;
  close: () => Promise<void>;
};

async function listenForAuthorizationCode(
  expectedState: string,
): Promise<AuthorizationCodeListener> {
  let server: http.Server | null = null;

  return await new Promise<AuthorizationCodeListener>((resolve, reject) => {
    let pendingResult:
      | { kind: "resolved"; code: string }
      | { kind: "rejected"; error: Error }
      | null = null;
    let codeResolver: ((code: string) => void) | null = null;
    let codeRejecter: ((error: Error) => void) | null = null;
    let handled = false;

    function settle(result: { kind: "resolved"; code: string } | { kind: "rejected"; error: Error }) {
      if (handled) {
        return;
      }

      handled = true;
      pendingResult = result;
      if (result.kind === "resolved") {
        codeResolver?.(result.code);
        return;
      }

      codeRejecter?.(result.error);
    }

    server = http.createServer((request, response) => {
      const requestUrl = new URL(request.url ?? "/", "http://127.0.0.1");
      if (requestUrl.pathname !== "/auth/callback") {
        response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Not found");
        return;
      }

      if (handled) {
        response.writeHead(409, { "Content-Type": "text/html; charset=utf-8" });
        response.end("<!doctype html><title>Connexion déjà traitée</title><p>Revenez à l’application en cours.</p>");
        return;
      }

      if (requestUrl.searchParams.get("state") !== expectedState) {
        response.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
        response.end("<!doctype html><title>Connexion échouée</title><p>Vous pouvez fermer cette fenêtre et revenir à l’application.</p>");
        settle({ kind: "rejected", error: new Error("Invalid Entra callback state.") });
        return;
      }

      const authError = requestUrl.searchParams.get("error");
      if (authError) {
        response.writeHead(400, { "Content-Type": "text/html; charset=utf-8" });
        response.end("<!doctype html><title>Connexion échouée</title><p>Vous pouvez fermer cette fenêtre et revenir à l’application.</p>");
        settle({ kind: "rejected", error: new Error("Entra sign-in was denied or failed.") });
        return;
      }

      const code = requestUrl.searchParams.get("code");
      if (!code) {
        response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
        response.end("Invalid callback.");
        settle({
          kind: "rejected",
          error: new Error("Missing authorization code from Entra callback."),
        });
        return;
      }

      response.writeHead(200, { "Content-Type": "text/html; charset=utf-8" });
      response.end("<!doctype html><title>Connexion réussie</title><p>Vous pouvez fermer cette fenêtre et revenir à AI Value Studio.</p>");
      settle({ kind: "resolved", code });
    });

    server.once("error", (error) => {
      reject(error);
    });

    server.listen(0, "127.0.0.1", () => {
      const address = server?.address();
      if (!address || typeof address === "string") {
        reject(new Error("Unable to bind Entra loopback callback."));
        return;
      }

      resolve({
        redirectUri: `http://127.0.0.1:${address.port}/auth/callback`,
        waitForCode: () =>
          new Promise<string>((resolveCode, rejectCode) => {
            if (pendingResult?.kind === "resolved") {
              resolveCode(pendingResult.code);
              return;
            }
            if (pendingResult?.kind === "rejected") {
              rejectCode(pendingResult.error);
              return;
            }

            codeResolver = resolveCode;
            codeRejecter = rejectCode;
          }),
        close: async () =>
          await new Promise<void>((resolveClose, rejectClose) => {
            server?.close((error) => {
              if (error) {
                rejectClose(error);
                return;
              }

              resolveClose();
            });
          }),
      });
    });
  });
}

export { listenForAuthorizationCode };
