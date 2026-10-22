## Standard customer return reasons — 22 October 2026

The customer-return form now has nine standard reasons: Excess / unused material, Wrong product ordered, Wrong product supplied, Wrong size / colour / shade, Damaged / broken goods, Defective product / quality issue, Customer changed requirement, Order cancelled, and Other reason. Other reason reveals a required explanation input; blank/whitespace-only input is blocked. Standard reasons hide the input. Existing reason strings are preserved, and the reason does not automatically change any line's Resellable checkbox.

Python/JavaScript syntax checks passed. In the isolated PostgreSQL-backed port-8009 browser demo, verified the list after loading an original invoice, default hidden explanation, standard reason save, required/whitespace validation, switching away from Other reason, and a custom reason save. One resellable unit and one non-restocked unit were returned against a fabricated invoice. Database readback confirmed exactly two active return records with the exact reasons, only one unit added to stock (16→17), total return credit 2500, net invoice 3750 and customer credit 2500. Invalid explanations created no returns. Old return/reversal history remained intact. A screenshot shows fabricated demo data only. No shop return, stock or customer balance was changed.

Frontend asset links were regenerated to prevent stale scripts after a browser reload. No backend/schema/dependency change was made, so the previous full-suite 98-test result below was not rerun for this display-only update. ZIP integrity and excluded-secret checks were repeated.

## Inventory reason dropdown — 22 October 2026

The receipt/adjustment form now has the nine requested reason options and a conditional Other reason input. The input is hidden, disabled and optional for standard choices; choosing Other adjustment reveals and requires it. Whitespace-only explanations are rejected. Standard reasons and `Other adjustment: explanation` are saved through the unchanged stock-adjustment API and shown in the ledger.

JavaScript syntax checks passed. In the isolated PostgreSQL-backed port-8009 browser demo, verified the default hidden field and all nine options, saved a New purchase received receipt, blocked empty and whitespace-only Other submissions, switched to a standard reason to hide the field, then saved Other adjustment with its explanation. Database readback confirmed exactly two valid +1 demo movements, quantity 14→16, and both exact ledger reasons; invalid submissions added no stock. The screenshot shows only fabricated demo data. No shop stock was changed. No backend/schema/dependency change was made; the previous full-suite 98-test result below was not rerun for this display-only change.

## Show all customers / invoices button fix — 22 October 2026

The button previously only cleared the selected-customer filter and restored the invoice dropdown. It now also opens a selectable customer list with name, mobile, address and posted-invoice count, a name/mobile filter, and 25-row paging. Choosing a row selects the customer in the existing picker and filters their invoices/return history. Customers without posted invoices display a clear message. Typing a new picker search hides the browser and clears stale invoice/return-item selections.

JavaScript syntax checking passed. Browser QA used six existing fabricated customers in the isolated port-8009 demo: the button showed all six, choosing Anita filtered to her one posted invoice, mobile filtering found Neha and selecting her showed no available posted invoices, and reopening restored all customers/invoices. No stock, invoice, customer or return record was changed. Paging with more than 25 records was not exercised in the browser. No backend/schema change was made, so the previous full-suite 98-test result below was not rerun for this display-only fix. ZIP integrity/excluded-secret checks were repeated.

## Editing, return/refund corrections and bill heading — 22 October 2026 (current)

**98 tests passed** in the complete suite on isolated PostgreSQL 18 / Python 3.12. This includes 20 new cases for versioned product/customer edits; preserved saved snapshots and stock; master-edit permissions, duplicate/stale inputs and reason validation; draft line/customer changes and rollback; converted-estimate protection; concurrent draft editors and edit-versus-post transactions; full return/refund reversals, safe retries/concurrent reversal, damaged stock, insufficient-stock rollback across multiple lines, dependent refunds, fractional rounding and corrected re-entry; owner permissions; and the exact printed heading for both document kinds. Existing authentication, inventory, billing and returns tests still pass. One existing Starlette/AnyIO deprecation warning remains.

Migration 007 was applied to the older restored test database, comparing all pre-existing columns/values across seven business tables. Existing values and row counts were preserved. This was a disposable restored database, not the shop database. A custom-format demo backup was also restored into a fresh temporary database; original correction log before/after data, return/refund reversal metadata and all compared row counts were identical. Login with its separately restored authenticator key succeeded. No production migration or real business correction was performed.

The isolated port-8009 browser demo used fabricated records and verified: product name/price edit; customer name/address edit with reason; mobile search and selecting a customer filtering both posted invoices and return history; a blocked return reversal while an active refund depended on the credit; owner-approved refund reversal followed by return reversal; draft quantity/price edit preserving the number and refreshing its total; and all five approval/reason entries in Correction history. Posted snapshots retained their original product/customer names. Database readback confirmed the edited draft did not change stock and the return reversal removed stock exactly once. Screenshots show fabricated demo records only.

A generated test invoice PDF was text-checked and rendered with the bundled PDF tools. Visual review confirmed the exact **ESTIMATE SANITARYWARE** heading and intact bill borders/columns. Automated tests verify that heading for estimates and invoices; document kinds and stock behavior are unchanged. No physical printing was performed. Python and JavaScript syntax checks passed. No new runtime dependencies were added. The new sidebar menu is scrollable on shorter desktop windows while keeping account/sign-out controls accessible; browser sign-out succeeded after this layout check.

Current boundaries: full-record reversals only; later returns for the same invoice items must be reversed first to retain cumulative rounding; dependent incorrect refunds must be reversed before the related return; posted/void documents and converted source estimates cannot be edited. Approval is the authenticated owner's explicit action, not a separate pending-approval queue. See README for usage and upgrade instructions. Previous-release verification below is historical.

## User management and mandatory authenticator verification — 22 October 2026 (previous release)

**78 tests passed** in the full suite on isolated PostgreSQL 18 / Python 3.12, including the original 64 business tests now using real authenticated owner sessions and 14 new authentication checks. One Starlette/AnyIO deprecation warning remains. No production account was created and no shop database migration was applied during this verification.

Coverage includes salted password hashes/encrypted secrets; first-time authenticator enrolment with no pre-verification business access; QR/secret delivery; one-use TOTP timesteps, challenges and recovery codes; persisted failed-attempt limits and password throttling; expired challenges/idle sessions; server-side Owner/Sales/Stock/Viewer restrictions; blocked stock reductions and unit changes for Stock users; last-owner protection; disabled accounts and revoked sessions; temporary-password changes; owner password/authenticator reset; local owner bootstrap/recovery; audit actor attribution; and alert polling that does not extend idle sessions. Tests use per-test security keys and disposable database credentials; no authentication bypass or default account is shipped.

The additive migration was applied to an older restored test database, comparing every existing column/value in seven business tables before/after; all were preserved. A fresh PostgreSQL custom-format dump of the fabricated demo database was restored into a new temporary database, preserving business/user/audit row counts. Its matching security key was copied separately, restored sessions/challenges/limits were cleared, and a real password + TOTP login succeeded against the restored database. The temporary restore database was then removed.

Browser verification used the isolated port-8009 demo and a fabricated, pre-enrolled owner: password step, authenticator prompt, successful code verification, Users & activity and My account screens. The user-management screenshot contains only fabricated demo information. New-credential creation/reset forms were tested through the backend, not submitted through browser automation. QR enrolment/recovery flows were verified in API tests; no real phone was enrolled. Python/JavaScript syntax checks and installed dependency consistency checks passed.

Not performed: independent security audit/penetration test, real owner/staff enrolment, clean-machine double-click installer testing, real-phone QR scan, production migration or production restore. Network/HTTPS deployment and passkeys remain future work. See README for required local owner setup, Windows file permissions and the separate security-key backup.

# Verification of this package

## Clickable alert-to-product navigation — 22 October 2026

Frontend-only change: product severity badges and product names open refreshed product stock details with batches, Add stock, and product-level threshold settings. Summary buttons open the matching product when only one matches, otherwise the priority-filtered alert list. Show all alerts clears the filter. Event delegation keeps links functional when the 30-second refresh replaces alert markup.

JavaScript syntax checking passed. Browser QA used the isolated port-8009 demo: Critical opened Ivory 600 x 600; Warning with two matching products showed exactly two rows, and selecting White Wash Basin opened its correct details; Add stock preselected that product's DEMO batch with an empty quantity; Notice opened Wall Tile Blue; Show all alerts restored all five demo alert rows. A screenshot records the Critical product detail. No stock movement was submitted. One demo-only alert threshold was adjusted to create the multiple-warning case; no shop data was changed. The backend suite was not rerun for this frontend-only change; its previous 64-test result remains below.

## Simplified direct unit selector — 22 October 2026 (current)

Per the user's correction, the Add stock form now has a direct Unit dropdown. Conversion setup, multiplication previews and unused-product correction forms are removed, as are conversion-write endpoints. New receipts use the entered number directly and atomically save the selected product unit for all batches. Old conversion data/movement snapshots are preserved for audit, and stale conversion requests are rejected.

The updated suite passed **64 tests** on isolated PostgreSQL 18 (the original 59 plus five replacement direct-unit tests). The obsolete ten conversion-feature tests were replaced, rather than counted as coverage for the removed behavior. Checks cover direct unit changes with no quantity conversion and safe retries; unchanged other-batch quantities, prices, thresholds and saved document units; rollback of unit changes on failed stock reduction; stale-unit rejection; and rejection of legacy conversion submissions. One existing Starlette/AnyIO deprecation warning remains.

In the isolated browser demo, a product with quantity 20 piece was changed to box while receiving 5; inventory became 25 box, and the new ledger entry was 5 box. The Unit dropdown persisted box, and no conversion panel existed. A screenshot records the simplified form. No shop stock or product units were changed during this QA. The current model cleanup only removes unused conversion model definitions; frontend/backend syntax checks were completed before packaging. Older conversion verification below describes the superseded feature and does not represent the current UI.

## Stock receipt units and unused-product unit correction — 22 October 2026

The final complete suite passed **69 tests** on isolated PostgreSQL 18, including ten new conversion tests. Covered: entered quantity/unit/factor/stock-unit snapshots; idempotent converted receipts; future-only factor changes and rejection of stale factors; preventing another product's receiving unit from being used; exact fractional conversion and rejection of results beyond three stock decimals; negative-stock protection; invalid/nonfinite factors and aliases for the existing stock unit; correcting unused units/prices with alert-threshold resets; blocking relabelling once stock/history/documents/conversions exist; and rejection of receipts opened before a base-unit change. All prior invoice, payment, return, alert, PDF and customer-search tests pass. One existing Starlette/AnyIO deprecation warning remains. JavaScript syntax checks passed.

Browser QA used only the isolated demo on port 8009: created a receiving unit box of 4 for a piece-based product, previewed five boxes as twenty pieces, saved, and verified twenty pieces in the batch and five boxes × four in the ledger. The screenshot shows the selected receiving unit and twenty-piece stock. The unused-stock-unit form was also used to change a different empty demo product from box to piece with a reviewed price; its batch unit changed and thresholds reset to zero. A stale-base-unit check was added after browser QA and verified in the final automated suite.

Migration 005 was applied to the older restored test database and every existing column value/row remained unchanged. No migration, stock receipt, conversion configuration or unit change was made in the user's shop database; startup applies the schema update after restart. No new runtime dependencies were added. The new sidebar menu is scrollable on shorter desktop windows while keeping account/sign-out controls accessible; browser sign-out succeeded after this layout check. Unit conversion is implemented for receipts/adjustments only; invoices, estimates, customer returns, prices and low-stock thresholds remain in the stock unit. Physical pack contents must be supplied by the user; no supplier-data lookup or automatic factor inference is implemented.

## Saved-batch visibility fix — 22 October 2026

The actual configured shop database was checked read-only and contained 24 batches named GENERAL. The missing list on Products & batches was a UI omission; no duplicate batches were created. A searchable Saved batches table was added, with SKU/name, batch code, colour, shade/size, quantity/unit and an Add stock shortcut. JavaScript syntax checking passed. In the running shop application, browser QA verified Saved batches (24), a ONE PIECE search returning the three matching GENERAL batches, and the Add stock shortcut selecting ONE PIECE 104 / GENERAL with a blank quantity field. No stock movement or other business data was written. A screenshot records the saved-batch list. The backend test suite was not rerun for this display-only change; the earlier 59-test result below remains its prior verification record.

## Customer name/mobile search — 22 October 2026

The suite passed **59 tests** on isolated PostgreSQL 18, including five new live search tests: partial case-insensitive names and duplicate-name identity/address details; full/partial mobile matching despite formatting/country prefixes; empty/no-result queries; deterministic 20-result caps and literal wildcard/injection-like input; and query-length validation. One existing Starlette/AnyIO deprecation warning remains. Frontend syntax checks passed. No migration or new dependency is needed.

Browser checks used fabricated customers in the isolated port-8009 demo, not the user's shop database. Two customers with the same name appeared with distinct mobiles, addresses and IDs. Up/Enter selected a result; editing the input cleared the selected ID and made the field invalid until a new result was selected. Searching the unformatted mobile found the formatted stored number, selecting it and saving produced the correct customer invoice. Estimate search and the no-results message were also verified. A screenshot shows the estimate picker with duplicate-name results. A final display-only adjustment keeps late results closed after focus leaves the input; this was syntax-checked. No large-customer-count load benchmark was performed. The running production app was not restarted or its database modified.

## Criticality-based stock alerts — 22 October 2026

The full suite passed **54 tests** on isolated PostgreSQL 18 (one existing Starlette/AnyIO deprecation warning). Twenty-two new cases cover threshold equality and fractional boundaries, zero/default levels, High/Medium/Low urgency, disabled products, invalid/nonfinite/over-precision thresholds, combined stock across batches, products with no batches, saving policies without changing catalogue/stock, missing products, severity/criticality/coverage ordering, and alert changes after invoice posting, voiding, receipts, adjustments and resellable/damaged customer returns. Both new and existing frontend scripts passed syntax checks. The additive migration was also applied to the older restored test database; all original values and rows were preserved.

Browser QA used only the separate demo database on port 8009. The overview showed one Out of stock, Critical, Warning and Notice alert. Saving a change from High to Medium changed that product's alert from Critical to Warning. A stock receipt made the product healthy; without clicking Refresh, the 30-second browser check reduced the alert count from four to three and retained an unsaved minimum-stock input of 12. Saving that minimum then restored a Critical alert for the High product at 11 units. A preview screenshot records the resulting dashboard. No business data was changed in the user's shop database, and its running process was left in place. It must be restarted to load this version and apply migration 004.

These are in-app alerts, not external notifications. No email/SMS/desktop push service, per-batch threshold, demand forecast, lead-time replenishment calculation or purchase-order generation is included or tested. Existing product alert levels are zero until configured; only zero-stock alerts appear with these defaults.

## Customer return update — 22 October 2026

The final suite passed **32 tests** on the isolated PostgreSQL 18 cluster (one existing Starlette/AnyIO deprecation warning). Ten new live tests verify: partial returns restore original-batch stock and reduce amount due; duplicate retry keys and excess quantities are safe; damaged goods receive credit without restocking; paid returns create refundable credit and refunds respect limits/retries; partly paid returns offset debt before refunding; concurrent returns cannot exceed quantities sold; concurrent refunds cannot exceed credit; a foreign invoice line causes the whole return to roll back; fractional returns credit exactly the original rounded line amount; drafts, estimates and void invoices reject returns. Existing sale, migration, payment and PDF checks also pass.

A browser walkthrough used a separate demo database: ten opening boxes, five sold and paid, two received back. Inventory showed seven boxes and a +2 return movement. The return screen showed credit 20; recording an actual-example cash refund of 20 produced zero remaining amount due/credit and a refund history entry. Only fabricated demo data was used. The user's running app on port 8000 was left alone; the QA server used port 8009 with a test-only Host/Origin adapter kept outside the package. The production Host/Origin checks were not relaxed. Both frontend JavaScript files passed syntax checking.

An updated invoice PDF was rendered and visually reviewed: the original gross amount remains 50, the footer displays return credit 20, refunded 20, net bill 30 and current balance zero. No separate return-note PDF or physical printer was tested. Customer return/refund reversal and transfers of credit between invoices remain future work. No migration or writes were performed against the user's shop database; startup applies the additive migration after the user restarts.

## Bill layout update — 22 October 2026

The new bill PDF was generated using the reference's 24 sample lines and reviewed visually on both rendered pages. The original 594.75 × 432 point media size, first-page subtotal of 32,430.00, final total of 62,620.00, cumulative quantities 112/157, carry-forward / brought-forward labels and total in words were checked. Invoice heading is deliberately INVOICE SANITARYWARE; estimates retain ESTIMATE SANITARYWARE. Draft/void labels and document numbers are retained. Fonts are read from Windows, not bundled.

The final updated suite passed **22 tests** against the disposable PostgreSQL 18 cluster: the original 18 plus three PDF/wording/wrapping cases and a live integration test covering Brand/Pack/Grade/Colour/Vehicle snapshots, estimate conversion and the PDF endpoint. One existing Starlette/AnyIO deprecation warning remains. A separate upgrade check applied migration 002 to the older restored test database and verified every original column value and row remained unchanged across all seven business tables. JavaScript syntax checking passed.

ReportLab 4.4.9, Pillow 12.2.0 and charset-normalizer 3.4.7 were installed from already-installed local distributions for this PC after a network download stalled. They are pinned in the setup requirements; dependency wheels are not included in the ZIP. The app's local virtual environment was updated as well as the isolated test environment. No connection or migration was performed against the user's actual shop database. The user's .env was preserved. The new PDF was rendered using Windows Verdana/Times fonts and both pages were visually checked. The updated forms/PDF iframe were not separately exercised in a live browser; a physical printer and alternate font fallbacks were not tested. The older starter verification remains below as a record of its original checks.

Performed on 22 October 2026 on Windows with Python 3.12 and a separate, disposable PostgreSQL **18.6** cluster bound to loopback port 55439. The user's existing PostgreSQL databases were not used. No test data, database credentials, virtual environment or temporary PostgreSQL cluster is included in this ZIP.

## Automated tests actually run

`python -m pytest -q`: **18 passed**, including 10 model/rounding cases and 8 live PostgreSQL integration tests. One dependency deprecation warning from Starlette/AnyIO was reported; no test failures remained.

Covered:

- Half-up monetary rounding, repeated batch rejection, zero/nonfinite/over-precision adjustment and payment validation.
- Estimates leave stock unchanged; converting twice returns the same invoice draft.
- Posting deducts stock once; posting a second time has no additional effect.
- Failure on a later invoice line rolls back earlier deductions, ledger writes and posting status.
- Voiding an unpaid posted invoice restores stock once; voided invoices cannot be posted again.
- Two competing sales for seven units from ten units yield one success and one conflict, leaving three units.
- Two competing payments cannot exceed the invoice total.
- Payment/adjustment/document retries return the original result; changed data under a reused key is rejected.
- Negative stock and overpayments are blocked; invoices with payments cannot be voided.
- Decimal line total is saved correctly; cross-site origin and invalid Host requests are rejected.
- Repeated database initialization applies the migration only once.

An initial assertion used `Decimal(float)` on a JSON value, producing a floating point representation artifact. It was corrected to compare the decimal text representation; server-side arithmetic and stored numeric totals were already correct. The complete final suite was rerun and passed.

JavaScript syntax was checked using Node's `--check`; it passed. Node is not required by the application.

## Browser walkthrough actually performed

Used the local app in a browser with the temporary database:

1. Created a tile product with a selling price of 800, a batch with shade/size, and a customer.
2. Received ten boxes and verified the inventory table showed ten.
3. Created a three-box estimate for 2,400 and converted it to an invoice draft.
4. Posted the invoice; verified the inventory table showed seven boxes and a −3 movement.
5. Recorded a payment of 1,000; verified payment history, total 2,400 and remaining balance 1,400.
6. Visually inspected the interface and saved a preview screenshot outside the source package.

## Backup and restore actually performed

Used PostgreSQL 18 client tools with the temporary database and temporary local folders:

- Ran the delivered backup helper three times.
- Verified exactly two completed dumps remained locally and two in a separate test folder representing a synced-folder destination.
- Compared filenames and SHA-256 checksums between both copies.
- Configured a missing destination folder and verified failure preserved the previous local dump files.
- Restored the newest archive with `pg_restore --single-transaction --exit-on-error` into a fresh database.
- Compared every row of products, batches, customers, documents, document lines, movements and payments against the source snapshot (1 product, 1 batch, 1 customer, 2 documents, 2 lines, 2 movements, 1 payment).
- Ran migrations on the restored database successfully.

## Not tested / not claimed

- No connection to the user's shop/production database and no configuration of its existing service.
- No actual Google Drive upload, deletion sync, cloud Trash cleanup or scheduled backup task.
- No Windows setup wizard/SmartScreen path on a second clean PC. The same pinned dependencies were installed in an isolated virtual environment; the FastAPI server and PostgreSQL tools were exercised directly. The double-click launcher's automatic browser-opening behavior was not separately tested end to end.
- No print-driver/PDF output validation, large catalogue load testing, fixed 8 GB memory benchmark, long-term soak test, power-loss simulation, or security penetration test.
- No other Python/PostgreSQL versions verified.

The ZIP contains source and setup helpers, not a bundled executable or offline dependency installer. First-time setup requires internet and the user's own database/password configuration.
