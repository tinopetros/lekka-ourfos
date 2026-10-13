# Phase 13: learnings

What this phase brings in, why it matters, and where to read about it. Notes from reading go under each.

## IAP: Identity-Aware Proxy

Google signs people in before a request reaches us, and hands us a signed header saying who they are. No login code, sessions or cookies of our own, and leaving the Workspace locks them out.

- [IAP for Cloud Run](https://cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run)
- [Getting the user's identity with signed headers](https://cloud.google.com/iap/docs/signed-headers-howto)

## BFF: Backend for Frontend

An API shaped for one UI, in front of the services that do the work. Ours keeps browsers away from the routes that post to Mifos.

- [Sam Newman, Backends For Frontends](https://samnewman.io/patterns/architectural/bff/)

## Pydantic, response models and OpenAPI

A Pydantic model is a type Python checks at runtime. As a FastAPI response model, it shapes what a route returns and describes it in OpenAPI, from which our TypeScript is generated. Firestore enforces no schema, so these models become its only definition.

- [Pydantic: Models](https://docs.pydantic.dev/latest/concepts/models/)
- [FastAPI: Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- [FastAPI: Generating Clients](https://fastapi.tiangolo.com/advanced/generate-clients/)
- [openapi-typescript](https://openapi-ts.dev/), and [openapi-fetch](https://openapi-ts.dev/openapi-fetch/), the client that calls the API through its types

## TanStack Query and Zustand: server state and client state

Data from the server is a cache of someone else's state: it goes stale, needs refetching, loading and error states. Query does all that. Zustand is for what only the browser knows, like a collapsed sidebar. Mixing them is the commonest React state mistake.

- [TkDodo, Practical React Query](https://tkdodo.eu/blog/practical-react-query), the series
- [TkDodo, Working with Zustand](https://tkdodo.eu/blog/working-with-zustand)

## React 19 and React Router 8

The UI's base. Router has three modes; we use data mode in a single-page app: routes as objects in one file, `createBrowserRouter`, no server rendering.

- [React 19](https://react.dev/blog/2024/12/05/react-19)
- [React Router: picking a mode](https://reactrouter.com/start/modes)

## shadcn and Tailwind 4

shadcn isn't a library: its components are copied into our code, ours to change, built on Radix for accessibility. Tailwind 4 is configured in CSS, not JavaScript.

- [shadcn/ui](https://ui.shadcn.com/docs)
- [Tailwind CSS v4](https://tailwindcss.com/blog/tailwindcss-v4)

## Structuring a React app

Features in their own folders, shared pieces apart. What keeps a growing UI easy to change.

- [bulletproof-react](https://github.com/alan2207/bulletproof-react)

## Firestore pagination

Lists page with cursors, the last document seen, not offsets: Firestore charges for every document an offset skips.

- [Paginate data with query cursors](https://firebase.google.com/docs/firestore/query-data/query-cursors)

## For later phases

Permissions, phase 15. Worth reading ahead.

- [Oso, Authorization Academy](https://www.osohq.com/academy): roles, relationships, and filtering lists by what you may see
- [OWASP, Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [Zanzibar, Google's authorization system](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/): where relationship-based access ends up at scale
- [monorepo.tools](https://monorepo.tools/): one repo or many, the trade-offs
