# AWS Serverless Shopping Website App

A full-stack serverless e-commerce application with an AI-powered shopping assistant, built on AWS using SAM, Vue.js, and Amazon Bedrock.

---

## Overview

This project demonstrates a production-style shopping cart microservice with an LLM-powered personal shopping agent. Users can browse products, manage their cart, and interact with an AI assistant that can search the catalog, inspect the cart, and perform confirmed cart actions.

---

## Architecture

| Layer | Technology |
|-------|-----------|
| **Frontend** | Vue.js 2, Vuetify, AWS Amplify SDK |
| **API** | Amazon API Gateway (REST) |
| **Compute** | AWS Lambda (Python 3.13) |
| **Database** | Amazon DynamoDB |
| **Auth** | Amazon Cognito |
| **AI Assistant** | Amazon Bedrock Agent (Nova Lite v1) |
| **CI/CD** | AWS Amplify Console / GitHub Actions |
| **IaC** | AWS SAM (CloudFormation) |

### Backend Services

| Stack | Purpose |
|-------|---------|
| `auth.yaml` | Cognito User Pool & App Client |
| `product-mock.yaml` | Mock product catalog API |
| `shoppingcart-service.yaml` | Cart CRUD, migration, checkout, DynamoDB Streams aggregation |
| `agent-service.yaml` | Bedrock Agent for AI shopping assistant |

---

## Prerequisites

- **Python** >= 3.13.0
- **AWS SAM CLI** >= 1.165.0
- **AWS CLI** (configured with credentials)
- **Node.js & Yarn** (for frontend)
- **boto3** (Python)
- **Amazon Bedrock** model enabled in your account/region (default: `amazon.nova-lite-v1:0`)

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/<your-username>/aws-serverless-shopping-cart.git
cd aws-serverless-shopping-cart
```

### 2. (Optional) Set AWS Profile

```bash
export AWS_PROFILE=<your-profile-name>
```

### 3. Deploy the Backend

```bash
make backend
```

This will:
- Create an S3 deployment bucket (auto-named with your account ID and region)
- Deploy the Auth, Product, Shopping Cart, and Agent stacks in order

### 4. Run the Frontend Locally

```bash
make frontend-serve
```

Access the app at **http://localhost:8080/**

> **Note:** CORS is configured for `http://localhost:8080`. Using `127.0.0.1` or a different port will cause CORS errors.

### 5. Create an Account

Click **Sign In** → **Create Account**. Use a valid email to receive the verification code.

---

## Alternative: Full Deployment via AWS Amplify Console

```bash
export GITHUB_REPO=https://github.com/<your-username>/aws-serverless-shopping-cart
export GITHUB_BRANCH=master
export GITHUB_OAUTH_TOKEN=<your-github-personal-access-token>

make amplify-deploy
```

Then go to the [AWS Amplify Console](https://console.aws.amazon.com/amplify/home), select **CartApp**, and click **Run Build**.

---

## API Endpoints

### Shopping Cart (`/cart`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/cart` | Get cart for current user (anonymous or authenticated) |
| POST | `/cart` | Add item to cart (body: `{productId, quantity}`) |
| POST | `/cart/migrate` | Merge anonymous cart into authenticated user's cart |
| POST | `/cart/checkout` | Checkout (empties cart) |
| PUT | `/cart/{product-id}` | Update item quantity |
| GET | `/cart/{product-id}/total` | Get aggregated total of a product across all carts |

### Products (`/product`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/product` | List all products |
| GET | `/product/{product_id}` | Get single product details |

### Assistant (`/assistant`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/assistant` | Send a message to the AI shopping assistant (requires auth) |

---

## AI Shopping Assistant

Signed-in users can chat with the assistant to:

- Search the product catalog ("Find fruit under $5")
- Inspect their cart ("What's in my cart?")
- Add/remove items ("Add two of the cheapest vegetables")
- Preview checkout ("Preview checkout and tell me the total")

The assistant uses Amazon Bedrock Agents with six purpose-built action tools. Cart-modifying actions require user confirmation.

---

## Key Design Decisions

- **Anonymous carts** persist via a UUID cookie (TTL: 1 day)
- **Authenticated carts** have a 7-day TTL
- **Cart migration** merges anonymous → authenticated on login (quantities summed)
- **DynamoDB Streams** power real-time aggregation of product quantities across all carts
- **Security**: The Bedrock Agent never sees Cognito tokens; user identity is resolved server-side

---

## Project Structure

```
AWS-Serverless-Shopping-WebSite-App-https/
├── backend/
│   ├── auth.yaml                    # Cognito stack
│   ├── product-mock.yaml            # Product catalog stack
│   ├── shoppingcart-service.yaml    # Cart service stack
│   ├── agent-service.yaml           # Bedrock agent stack
│   ├── shopping-cart-service/       # Cart Lambda handlers (Python)
│   ├── product-mock-service/        # Product Lambda handlers (Python)
│   ├── agent-service/               # Agent Lambda handlers (Python)
│   └── layers/                      # Shared Lambda layer
├── frontend/
│   ├── src/                         # Vue.js application source
│   ├── public/                      # Static assets
│   └── package.json
├── amplify-ci/                      # Amplify Console CloudFormation template
├── amplify.yml                      # Amplify build spec
├── Makefile                         # Top-level build orchestration
└── README.md
```

---

## Cleanup

```bash
make backend-delete
```

If deployed via Amplify, also delete the **CartApp** stack from CloudFormation.

---

## License

MIT-0 License. See [LICENSE](./AWS-Serverless-Shopping-WebSite-App-https/LICENSE).
