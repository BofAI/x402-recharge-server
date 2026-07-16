FROM node:22-slim AS build

WORKDIR /app

COPY package.json package-lock.json tsconfig.json ./
RUN npm ci

COPY config ./config
COPY src ./src
RUN npm run build

FROM node:22-slim

ENV NODE_ENV=production \
    BANKOFAI_ENV=dev \
    X402_FACILITATOR_URL=https://tn-facilitator.bankofai.io \
    TRON_RPC_URL=

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci --omit=dev

COPY --from=build /app/dist ./dist
COPY config ./config

EXPOSE 8000

CMD ["node", "dist/server.js"]
