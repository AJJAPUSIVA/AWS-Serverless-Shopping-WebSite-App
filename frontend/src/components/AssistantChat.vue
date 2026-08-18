<template>
  <div>
    <v-btn
      aria-label="Open shopping assistant"
      class="assistant-button"
      color="accent"
      dark
      fab
      fixed
      bottom
      right
      @click="open = true"
    >
      <v-icon>mdi-message-text</v-icon>
    </v-btn>

    <v-dialog v-model="open" max-width="520" scrollable>
      <v-card class="assistant-card">
        <v-card-title class="primary accent--text">
          Shopping Assistant
          <v-spacer />
          <v-btn icon aria-label="Close shopping assistant" @click="open = false">
            <v-icon color="white">mdi-close</v-icon>
          </v-btn>
        </v-card-title>

        <v-card-text ref="messageList" class="assistant-messages pt-4">
          <div
            v-for="(item, index) in messages"
            :key="index"
            :class="['assistant-message', item.role]"
          >
            {{ item.text }}
          </div>

          <v-alert v-if="!currentUser" type="info" outlined>
            Sign in to let the assistant securely read and update your cart.
            <v-btn small text color="primary" to="/auth" @click="open = false">Sign in</v-btn>
          </v-alert>

          <div v-if="sending" class="assistant-typing">
            <v-progress-circular indeterminate size="18" width="2" color="accent" />
            Thinking…
          </div>
        </v-card-text>

        <v-divider />
        <v-card-actions>
          <v-text-field
            v-model="draft"
            :disabled="!currentUser || sending"
            :error-messages="errorMessage"
            aria-label="Message the shopping assistant"
            autocomplete="off"
            counter="2000"
            dense
            hide-details="auto"
            maxlength="2000"
            placeholder="Try: Find fruit under $5"
            @keyup.enter="send"
          />
          <v-btn
            :disabled="!canSend"
            :loading="sending"
            aria-label="Send message"
            color="accent"
            icon
            @click="send"
          >
            <v-icon>mdi-send</v-icon>
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script>
import { mapGetters } from "vuex";
import { askAssistant } from "@/backend/api.js";

export default {
  name: "assistant-chat",
  data() {
    return {
      open: false,
      draft: "",
      sending: false,
      errorMessage: "",
      sessionId: null,
      messages: [
        {
          role: "assistant",
          text: "Hi! I can find products, compare prices, and help manage your cart."
        }
      ]
    };
  },
  computed: {
    ...mapGetters(["currentUser"]),
    canSend() {
      return Boolean(this.currentUser && !this.sending && this.draft.trim());
    }
  },
  watch: {
    currentUser(value) {
      if (!value) {
        this.sessionId = null;
      }
    }
  },
  methods: {
    scrollToLatest() {
      this.$nextTick(() => {
        const list = this.$refs.messageList;
        if (list) {
          list.scrollTop = list.scrollHeight;
        }
      });
    },
    async send() {
      if (!this.canSend) return;

      const message = this.draft.trim();
      this.messages.push({ role: "user", text: message });
      this.draft = "";
      this.errorMessage = "";
      this.sending = true;
      this.scrollToLatest();

      try {
        const response = await askAssistant(message, this.sessionId);
        this.sessionId = response.sessionId;
        this.messages.push({ role: "assistant", text: response.message });
        await this.$store.dispatch("fetchCart");
      } catch (error) {
        this.errorMessage =
          (error.response && error.response.data && error.response.data.message) ||
          "The assistant is unavailable. Please try again.";
      } finally {
        this.sending = false;
        this.scrollToLatest();
      }
    }
  }
};
</script>

<style scoped>
.assistant-button {
  bottom: 24px !important;
  right: 24px !important;
  z-index: 6;
}

.assistant-card {
  height: min(680px, 82vh);
}

.assistant-messages {
  background: #f7f8fa;
  overflow-y: auto;
}

.assistant-message {
  border-radius: 14px;
  margin-bottom: 12px;
  max-width: 88%;
  padding: 10px 12px;
  white-space: pre-wrap;
}

.assistant-message.assistant {
  background: white;
  border: 1px solid #e4e7eb;
}

.assistant-message.user {
  background: var(--amazonOrange);
  color: white;
  margin-left: auto;
}

.assistant-typing {
  align-items: center;
  color: #5f6368;
  display: flex;
  gap: 8px;
}
</style>
