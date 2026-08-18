/**
 * Authentication module using Amazon Cognito Identity JS SDK.
 * Handles sign-in, sign-up, verification, and session management.
 */
const Auth = (() => {
  const poolData = {
    UserPoolId: CONFIG.USER_POOL_ID,
    ClientId: CONFIG.USER_POOL_CLIENT_ID
  };

  const userPool = new AmazonCognitoIdentity.CognitoUserPool(poolData);
  let currentUser = null;

  // DOM references
  const modal = () => new bootstrap.Modal(document.getElementById("authModal"));
  const btnAuth = () => document.getElementById("btn-auth");
  const btnSignout = () => document.getElementById("btn-signout");

  function init() {
    // Check for existing session
    const cognitoUser = userPool.getCurrentUser();
    if (cognitoUser) {
      cognitoUser.getSession((err, session) => {
        if (!err && session.isValid()) {
          currentUser = cognitoUser;
          onSignedIn();
        }
      });
    }

    // Form handlers
    document.getElementById("signin-form").addEventListener("submit", handleSignIn);
    document.getElementById("register-form").addEventListener("submit", handleRegister);
    document.getElementById("confirm-form").addEventListener("submit", handleConfirm);
  }

  function getIdToken() {
    return new Promise((resolve, reject) => {
      if (!currentUser) return resolve(null);
      currentUser.getSession((err, session) => {
        if (err || !session.isValid()) return resolve(null);
        resolve(session.getIdToken().getJwtToken());
      });
    });
  }

  function isSignedIn() {
    return currentUser !== null;
  }

  function showModal() {
    showSignIn();
    bootstrap.Modal.getOrCreateInstance(document.getElementById("authModal")).show();
  }

  function showSignIn() {
    document.getElementById("signin-form").classList.remove("d-none");
    document.getElementById("register-form").classList.add("d-none");
    document.getElementById("confirm-form").classList.add("d-none");
    document.getElementById("authModalLabel").textContent = "Sign In";
  }

  function showRegister() {
    document.getElementById("signin-form").classList.add("d-none");
    document.getElementById("register-form").classList.remove("d-none");
    document.getElementById("confirm-form").classList.add("d-none");
    document.getElementById("authModalLabel").textContent = "Create Account";
  }

  function showConfirm() {
    document.getElementById("signin-form").classList.add("d-none");
    document.getElementById("register-form").classList.add("d-none");
    document.getElementById("confirm-form").classList.remove("d-none");
    document.getElementById("authModalLabel").textContent = "Verify Account";
  }

  function handleSignIn(e) {
    e.preventDefault();
    const email = document.getElementById("signin-email").value.trim();
    const password = document.getElementById("signin-password").value;
    const errorEl = document.getElementById("signin-error");
    errorEl.classList.add("d-none");

    const authDetails = new AmazonCognitoIdentity.AuthenticationDetails({
      Username: email,
      Password: password
    });

    const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
      Username: email,
      Pool: userPool
    });

    cognitoUser.authenticateUser(authDetails, {
      onSuccess(session) {
        currentUser = cognitoUser;
        bootstrap.Modal.getOrCreateInstance(document.getElementById("authModal")).hide();
        onSignedIn();
      },
      onFailure(err) {
        errorEl.textContent = err.message || "Sign in failed.";
        errorEl.classList.remove("d-none");
      }
    });
  }

  function handleRegister(e) {
    e.preventDefault();
    const email = document.getElementById("register-email").value.trim();
    const password = document.getElementById("register-password").value;
    const errorEl = document.getElementById("register-error");
    errorEl.classList.add("d-none");

    const attributeList = [
      new AmazonCognitoIdentity.CognitoUserAttribute({ Name: "email", Value: email })
    ];

    userPool.signUp(email, password, attributeList, null, (err, result) => {
      if (err) {
        errorEl.textContent = err.message || "Registration failed.";
        errorEl.classList.remove("d-none");
        return;
      }
      // Show confirm form with email pre-filled
      document.getElementById("confirm-email").value = email;
      showConfirm();
    });
  }

  function handleConfirm(e) {
    e.preventDefault();
    const email = document.getElementById("confirm-email").value.trim();
    const code = document.getElementById("confirm-code").value.trim();
    const errorEl = document.getElementById("confirm-error");
    errorEl.classList.add("d-none");

    const cognitoUser = new AmazonCognitoIdentity.CognitoUser({
      Username: email,
      Pool: userPool
    });

    cognitoUser.confirmRegistration(code, true, (err, result) => {
      if (err) {
        errorEl.textContent = err.message || "Verification failed.";
        errorEl.classList.remove("d-none");
        return;
      }
      showSignIn();
      document.getElementById("signin-email").value = email;
    });
  }

  function onSignedIn() {
    btnAuth().classList.add("d-none");
    btnSignout().classList.remove("d-none");

    // Migrate anonymous cart to user cart
    if (Cart.getItems().length > 0) {
      Cart.migrate();
    } else {
      Cart.fetch();
    }

    // Enable assistant
    Assistant.onAuthChange(true);
  }

  function signOut() {
    if (currentUser) {
      currentUser.signOut();
    }
    currentUser = null;
    btnAuth().classList.remove("d-none");
    btnSignout().classList.add("d-none");

    // Reset cart and assistant
    Cart.fetch();
    Assistant.onAuthChange(false);
  }

  return {
    init,
    getIdToken,
    isSignedIn,
    showModal,
    showSignIn,
    showRegister,
    showConfirm,
    signOut
  };
})();
