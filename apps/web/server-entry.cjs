// Production entrypoint wrapping Next's standalone server.js.
//
// Next's /api/* rewrite forwards request headers as-is and does NOT add the client's address to
// X-Forwarded-For. FastAPI trusts X-Forwarded-For from this hop (uvicorn --proxy-headers with
// FORWARDED_ALLOW_IPS=<web>), so a client-sent header would let anyone pick their own
// rate-limit bucket. This is the edge: overwrite the header with the real socket address.
// (Behind a load balancer that sets X-Forwarded-For itself, route /api/* at the LB instead.)
const http = require("node:http");

const createServer = http.createServer;
http.createServer = function patchedCreateServer(...args) {
  const server = createServer.apply(this, args);
  server.prependListener("request", (req) => {
    const ip = req.socket.remoteAddress;
    if (ip) req.headers["x-forwarded-for"] = ip.replace(/^::ffff:/, "");
    else delete req.headers["x-forwarded-for"];
  });
  return server;
};

require("./server.js");
