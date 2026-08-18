/**
 * Configuration - Update these values after deploying the backend.
 * These correspond to the SSM parameters created by the SAM stacks.
 */
const CONFIG = {
  REGION: "us-east-1",                          // Your AWS region
  USER_POOL_ID: "us-east-1_XXXXXXXXX",         // From /serverless-shopping-cart-demo/auth/user-pool-id
  USER_POOL_CLIENT_ID: "xxxxxxxxxxxxxxxxxxxxxxxxxx", // From /serverless-shopping-cart-demo/auth/user-pool-client-id
  CART_API_URL: "https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod",      // Cart API Gateway URL
  PRODUCTS_API_URL: "https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod",  // Product API Gateway URL
  ASSISTANT_API_URL: "https://xxxxxxxxxx.execute-api.us-east-1.amazonaws.com/Prod"  // Assistant API Gateway URL
};
