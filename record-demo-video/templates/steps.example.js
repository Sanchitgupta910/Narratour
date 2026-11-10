// steps.js: one narrated demo. Copy this into the work folder and edit it.
//
// Each step is a line or two of narration (`say`) plus what happens on screen
// while it is spoken (`run`). The next step starts once this step's narration
// has finished, so keep the actions about as long as the words.
//
// Everything filmed should go through T (click, type, hover...), so the drawn
// cursor visibly moves and clicks. T is also passed to setup() and check().
window.__DEMO = {
  // Opened fresh before every practice run and recording.
  startUrl: "http://localhost:3000/settings/team",

  // Optional: true once the page has finished loading its data.
  ready: () => !!document.querySelector("table tbody tr"),

  // Optional: runs before recording starts and is not filmed. Good for closing
  // banners, picking a date range, or turning on columns the demo needs.
  setup: async (T) => {
    const dismiss = T.button("Dismiss");
    if (dismiss) dismiss.click(); // plain clicks are fine here, nobody sees them
    await T.sleep(300);
  },

  // Optional: words the voice should say differently. Captions keep the original.
  pronounce: { "SSO": "S S O", "CSV": "C S V" },

  // Optional: a snapshot after every step. The practice run prints it, so you
  // can check that what the narration claims really happened.
  check: (T) => ({
    rows: T.$$("table tbody tr").length,
    dialog: !!T.$("[role=dialog]"),
  }),

  steps: [
    {
      say: "This is the team page. Let's invite someone new.",
      run: async (T) => {
        await T.hover("Invite member");
      },
    },
    {
      say: "I'll click Invite member and type their email.",
      run: async (T) => {
        await T.click("Invite member");
        await T.waitFor("[role=dialog]");
        await T.type("Email address", "sam@example.com");
      },
    },
    {
      say: "They should be an admin, so I'll pick that role.",
      run: async (T) => {
        await T.click("Role");
        await T.click(T.byText("Admin", "[role=option]"));
      },
    },
    {
      say: "Send invite. The new person shows up at the bottom, marked as pending.",
      run: async (T) => {
        await T.click("Send invite");
        const row = await T.waitFor(() => T.byText(/sam@example\.com/, "table tbody tr"));
        await T.hover(row);
        // Whatever a step returns is printed by the practice run.
        return T.text(row);
      },
      timeout: 40, // seconds; the default is 30
    },
    {
      say: "And that's it. They'll get an email with a link to join.",
      run: async (T) => {
        await T.sleep(400);
      },
    },
  ],
};
