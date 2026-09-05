import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { makeRouter, queryClient } from "./router";
import "./styles.css";

const router = makeRouter(queryClient);
const mount = document.getElementById("root");
if (mount === null) throw new Error("index.html declares no #root to mount into");

createRoot(mount).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
