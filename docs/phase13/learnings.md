# Phase 13: learnings

What this phase brings in, why it matters, and where to read about it. Notes from reading go under each.

## IAP: Identity-Aware Proxy

Google signs people in before a request reaches us, and hands us a signed header saying who they are. No login code, sessions or cookies of our own, and leaving the Workspace locks them out.

- Links:
  - [IAP](https://docs.cloud.google.com/iap/docs)
    - [Conceptual Overview](https://docs.cloud.google.com/iap/docs/concepts-overview)
  - [Getting the user's identity with signed headers](https://cloud.google.com/iap/docs/signed-headers-howto)
- The general idea here is one can more easily expose an app publicly and have strong authentication without necessarily having client-side software like a VPN
- IAP is a server that will sit in front of the runtime and check authorization as well as other configurable attributes such as device, location, etc before allowing access
- IAP passes JWTs that can be further verified in runtime and also used to extract user info - be sure to use the appropriate public keys

## BFF: Backend for Frontend

An API shaped for one UI, in front of the services that do the work. Ours keeps browsers away from the routes that post to Mifos.

- [Sam Newman, Backends For Frontends](https://samnewman.io/patterns/architectural/bff/)

## Pydantic, response models and OpenAPI

A Pydantic model is a type Python checks at runtime. As a FastAPI response model, it shapes what a route returns and describes it in OpenAPI, from which our TypeScript is generated. Firestore enforces no schema, so these models become its only definition.

- [Pydantic: Models](https://docs.pydantic.dev/latest/concepts/models/)
- [FastAPI: Response Model](https://fastapi.tiangolo.com/tutorial/response-model/)
- [FastAPI: Generating Clients](https://fastapi.tiangolo.com/advanced/generate-clients/)
- [openapi-typescript](https://openapi-ts.dev/), and [openapi-fetch](https://openapi-ts.dev/openapi-fetch/), the client that calls the API through its types
- I certainly can learn more here still, but from a general scan, it makes sense that pydantic essentially enables well-typed validatable python classes, these work well with FastAPI and it can spit them out as an api spec and typescript or JSON types as well etc.

## TanStack Query and Zustand: server state and client state

Data from the server is a cache of someone else's state: it goes stale, needs refetching, loading and error states. Query does all that. Zustand is for what only the browser knows, like a collapsed sidebar. Mixing them is the commonest React state mistake.

- [TkDodo, Practical React Query](https://tkdodo.eu/blog/practical-react-query), the series
  - This is a good read to begin with
  - Cool to know React Query handles server state fetching, caching etc. with a given `staleTime`
  - It generally seems to be a hook that fetches data (via any function that returns a promise) based on a queryKey (similar to dependency array for useEffect)
- [TkDodo, Working with Zustand](https://tkdodo.eu/blog/working-with-zustand)
  - I really like the idea of exporting custom hooks as selectors from the store and not redoing selectors all the time, quite nifty indeed and cleaner imo
  - Interestingly, this even helps save on rerenders, quite nice
  - Keep the selectors separate too, very nice
  - Actions can be exported in one big hook including actions since the do not change
  - It looks like the advice is also to have multiple stores and keep focus specific e.g. in this scenario user, forms, journal_entries etc. are best as separate stores
    - well but only user will likely be in zustand here since server data will come from the server
  - Zustand and React Query end up working together when we take state from Zustand because it is used as a key in React Query e.g. a user filter etc

## React 19 and React Router 8

The UI's base. Router has three modes; we use data mode in a single-page app: routes as objects in one file, `createBrowserRouter`, no server rendering.

- [React 19](https://react.dev/blog/2024/12/05/react-19)
- [React Router: picking a mode](https://reactrouter.com/start/modes)
- I think I have some React revision in order tbh, and Typescript and Python too, enough of the basics so that I can read code better and faster as I step into the work that I am about to do.
- The best approach here is likely small broad scans at a time and selective deep-dives as needed

## shadcn and Tailwind 4

shadcn isn't a library: its components are copied into our code, ours to change, built on Radix for accessibility. Tailwind 4 is configured in CSS, not JavaScript.

- [shadcn/ui](https://ui.shadcn.com/docs)
- [Tailwind CSS v4](https://tailwindcss.com/blog/tailwindcss-v4)

## Structuring a React app

Features in their own folders, shared pieces apart. What keeps a growing UI easy to change.

- [bulletproof-react](https://github.com/alan2207/bulletproof-react)
- Will be curious to see how much of this we actually end up using
- Finally learnt what absolute imports are and how they help in typescript so we do not always have to keep updating relative imports as files move around
- I actually do really like this for FE - even just as a starting point for personal projects honestly, just so there is a standard to hold to start
- Standards can always be improved and changed, but having a starting off point does go a long way indeed
- This is pretty golden, notes on state, forms, testing, error handling e.g. on apis - I am convinced to use most of the remainder of my sabbatical pre-Arlo on this and hardening whatever it is I am building, esp. in the FE, on this before going any further. BE will be hardened on the Google FDE standard as I understood it from my time there - and I will learn AWS in the process as well
- I may not master everything and that is okay, the goal is a revision / survey of what I will likely use, enough to have taste and be able to read code well and direct AI appropriately
- [This alone](https://github.com/alan2207/bulletproof-react/blob/master/docs/additional-resources.md) seems to be more than plenty for what I need to seed my learning, I am so grateful and should not be shy to spend when needed
  - When you do this, just try to learn / harden one thing at a time, even if only a survey vs. mastering it all instantly

## Firestore pagination

Lists page with cursors, the last document seen, not offsets: Firestore charges for every document an offset skips.

- [Paginate data with query cursors](https://firebase.google.com/docs/firestore/query-data/query-cursors)

## For later phases

Permissions, phase 15. Worth reading ahead.

- [Oso, Authorization Academy](https://www.osohq.com/academy): roles, relationships, and filtering lists by what you may see
- [OWASP, Authorization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html)
- [Zanzibar, Google's authorization system](https://research.google/pubs/zanzibar-googles-consistent-global-authorization-system/): where relationship-based access ends up at scale
- [monorepo.tools](https://monorepo.tools/): one repo or many, the trade-offs
