# Shivam Tiles — local Windows starter

## Customer return reason dropdown

After choosing the original invoice and loading its items, choose **Reason for return**: Excess / unused material, Wrong product ordered, Wrong product supplied, Wrong size / colour / shade, Damaged / broken goods, Defective product / quality issue, Customer changed requirement, Order cancelled, or Other reason.

**Other reason** shows a required **Other return reason** text box; blank and whitespace-only explanations cannot be saved. The return history retains the standard reason, or `Other reason: your explanation`. Existing saved reasons remain unchanged. Select **Resellable** separately for each item: choosing a reason does not change stock handling automatically. Uncheck it for damaged/defective items that cannot be sold again. Original invoice quantities, credit limits, owner permissions and reversal approval rules are unchanged.

This is a display update with versioned asset links. Reload the browser page to pick up the new form; the app's Refresh button reloads data only. No new dependency, database migration or server restart is required.

## Inventory reason dropdown

In **Inventory → Receive or adjust stock**, choose a reason: Opening stock, New purchase received, Stock count correction — increase, Stock count correction — decrease, Damaged / broken goods, Return to supplier, Samples / display use, Lost / missing stock, or Other adjustment.

Choosing **Other adjustment** shows an **Other reason** text box. An explanation is required; blank or whitespace-only entries cannot be saved. Switching to a standard reason hides the text box. The ledger records the selected reason, or `Other adjustment: your explanation`. Enter positive quantities for additions and negative quantities for removals; manual reductions remain owner-only. Unit behavior is unchanged. This display update needs only Ctrl+F5 after installation; no new dependency, restart or database migration is required.

## Editing and corrections — version 0.6.0

**Customer-list button fix:** press Ctrl+F5 in the browser after updating the source. Show all customers / invoices now opens a selectable, searchable customer list as well as clearing the invoice filter. This display fix needs no restart, new dependency or migration.

**Enable this update:** back up the database and your separate `.security/auth.key`, stop the app with Ctrl+C and start **Start-TileStock.bat** again. Startup applies additive migration `007_editing_corrections.sql`. Refresh the browser with Ctrl+F5. No new Python dependencies or owner setup are needed when upgrading from 0.5.0. For a different installation, replace source from the ZIP while retaining `.env`, `.venv`, `.security` and backups. No demo records or accounts are imported.

### Bill title

The printed heading is exactly **ESTIMATE SANITARYWARE** for both estimates and invoices, as requested. This changes the displayed heading only: document types, numbers, draft/void markings, posting and stock deductions continue to work as before.

### Edit products and customers

- **Products & batches → Product catalogue:** search by name/SKU and choose **Edit product**. Owners and Stock users may edit SKU, name, brand, pack, grade, selling price, informational area and stock-alert settings. The unit is read only here; owners change it using the existing Inventory receipt unit selector.
- **Customers:** search by name/mobile, choose **Edit customer**, change name/mobile/address, enter a reason and save. Owners and Sales users may edit customers; Viewer users cannot edit.
- Stock numbers are preserved. Existing estimate/invoice line and customer snapshots are not rewritten by master edits. New documents use the updated details; explicitly editing a draft refreshes its saved customer/product details. Customer IDs remain the same, so an edited customer still owns their older invoices and returns, even when their saved bill name differs.
- A reason is required. Version checks reject saving an old editor after another change; close it, refresh and review the new values. Retries of the same edit do not apply it twice.

### Search customers on the return screen

In **Customer returns**, type a name or mobile number and select a matching customer. Both **Original invoice** and **Return history** then show that customer's records. Mobile matching ignores punctuation, as on the invoice picker. Only posted invoices can receive returns. Editing the search text clears the old selection and loaded return items to prevent using a different customer's invoice by accident. **Show all customers / invoices** removes the filter and opens a selectable customer list with names, mobile numbers, addresses and posted-invoice counts. Filter this list by name/mobile and choose a customer to see their invoices. The list shows 25 customers per page with Previous/Next buttons. Customers without posted invoices remain visible and show a clear message when chosen. You may still choose an original invoice directly when no customer filter is active.

### Correct a draft with owner approval

Sign in as an **Owner**, open a draft estimate/invoice, and choose **Edit draft**. Change customer, batches, quantities, unit prices, notes or vehicle number. Enter a correction reason and click **Approve & save draft**. The signed-in owner approves the action; a second user's approval queue is not implemented. The document ID/number remains unchanged and no stock moves until the invoice is posted. Sales users may create drafts but must ask an owner to correct them.

Posted/void documents cannot be edited. An estimate with a linked invoice cannot be edited; edit its invoice draft instead. Original draft details and replacement details are retained in the correction log. A conflicting edit or posting causes a stale editor to be rejected, rather than overwriting the other change.

### Reverse an incorrect return or refund

Sign in as an **Owner**. Open the return from **Customer returns → View**, choose **Reverse return**, enter a reason and click **Approve & reverse**. This reverses the whole return: resellable quantities previously added are removed from their original batches, credit is removed from invoice balances, and the sold quantities become returnable again. Damaged/non-restocked lines do not move stock. Original return lines, amounts and stock entries stay in history, with compensating stock entries and a Reversed status.

If goods have already been sold and not enough stock remains, reversal is blocked and the complete transaction rolls back. If later active returns involve the same original invoice items, reverse those later returns first. This preserves the exact cumulative rounding of fractional credits. Returns for unrelated invoice items do not prevent reversal. Enter correct replacement returns afterwards when needed; do not also adjust stock manually for the same goods.

For a mistaken refund, open the original invoice and choose **Reverse refund** beside that refund record. Enter a reason and approve it. Its amount is excluded from refunded totals, restoring the correct customer balance; original amount/method/reference and reversal reason remain recorded. **This records a correction only and does not transfer or recover money.** Use it only for a mistaken entry or funds actually recovered. You may then record the correct refund separately.

A return reversal is blocked if it would leave active refunds larger than the remaining credit. Reverse the incorrect refund record(s) first, then the return. Partial reversal of one record and automatic partial adjustment of dependent refunds are not implemented; reverse the full record and re-enter corrected details. Repeated/concurrent reversal requests cannot move stock twice. Once all returns are reversed, an otherwise unpaid invoice can be voided normally; posted bills still cannot be edited.

### Correction history and boundaries

Owners can open **Correction history** for the latest 500 corrections, including approving user/email, action, record and required reason. Before/after data is retained in the database correction log; the screen shows the approval summary. Master-edit approvals may be performed by the permitted Sales/Stock role; draft and reversal approvals require an Owner. The existing Users & activity log also records the action. Backups automatically include correction/version/reversal data.

Future work includes partial correction of posted documents, a separate pending-approval workflow, correction-history detail/diff screens, batch master editing, tax credit-note PDFs and reversing ordinary invoice payments. These are not added by this update.

## User accounts and authenticator verification — version 0.5.0

This update adds mandatory email + password + authenticator-app verification, four roles, an owner-only user-management screen and an activity log. It supersedes older installation notes below about starting without authentication. No email account or internet connection is needed for sign-in after setup. Keep the Windows and phone clocks set correctly.

### Enable on your existing installation

1. Run **Backup-Windows.bat** before upgrading. Stop the running application console with Ctrl+C.
2. Your local source has been updated. Run **Setup-Windows.bat** to install the new libraries. For another installation, extract the ZIP and replace source files while retaining your `.env`, `.venv`, `backups` and `.security` folder, if present. Never replace the business database with a demo database.
3. Run **Setup-Owner.bat** in the application folder. It applies the additive migration `006_users_auth.sql`, then asks for the first owner's email, display name and a password of at least 12 characters. Password entry is hidden. No default account/password exists. The setup tool refuses to create a new first owner if users already exist.
4. Run **Start-TileStock.bat**, refresh the browser with Ctrl+F5 and sign in with that email and password. Scan the displayed QR code using Google Authenticator, Microsoft Authenticator or another standard TOTP authenticator. Alternatively enter the displayed setup key manually. Enter the current six-digit code to complete enrolment.
5. Save the ten recovery codes privately before continuing. Each code works once in place of an authenticator code. Do not share the QR code, setup key or recovery codes.
6. Open **Users & activity** to add staff. Give each person their temporary password privately. Each person enrols their own authenticator and changes the temporary password before gaining access. They then sign in again using their new password and a fresh authenticator code. Codes already used for login cannot be reused; wait for the next code if needed.

Existing products, stock, invoices and payments are retained. Existing records are not retrospectively assigned to users. New business changes and account actions record the actor; there is no automatic import of Windows users.

| Role | Permitted actions |
| --- | --- |
| Owner | All business actions; users, activity, returns, refunds, voiding and manual stock reductions/unit changes |
| Sales | Read business data; add/edit customers; create estimates/invoices, convert/post and record payments |
| Stock | Read products, batches, stock ledger and alerts; add/edit products, add batches, configure alerts and receive positive stock in its existing unit; no customer/sales records |
| Viewer | Read business data and PDFs; no business changes |

Every account may change its own password and replace recovery codes under **My account**. Replacing recovery codes requires its password and a fresh authenticator or unused recovery code; previous recovery codes stop working. Owners can edit staff roles/names, disable accounts and set temporary passwords. These actions revoke that user's existing sessions. Password resets keep the authenticator requirement. The last active owner cannot be disabled or demoted; owners cannot demote/disable themselves.

If a staff member loses their phone and all recovery codes, verify their identity, then use **Reset authenticator** in Users & activity. This requires the owner's own password and fresh second factor, invalidates the staff member's sessions and old recovery codes, and requires new enrolment. An owner who loses access can run **Recover-Owner.bat** locally, enter the existing owner's email and set a new password, then enrol again. This recovery tool requires trusted access to the application directory and database credentials; restrict those files and Windows access. It cannot create a new owner and is not an unauthenticated web reset endpoint.

### Security and backup details

Passwords are salted PBKDF2-HMAC-SHA256 hashes (600,000 iterations). Authenticator secrets are encrypted using the per-installation `.security/auth.key`; random session/challenge/recovery tokens are stored as hashes. Sessions use HttpOnly/SameSite=Strict cookies, expire after 8 hours or 30 minutes idle, and are revoked on account/password changes. Login challenges last five minutes with at most five code attempts; password/code endpoints also limit repeated attempts. A successful code timestep or recovery code is consumed once. First-time enrolment provides no business access until verification completes. Business permissions are checked on the server as well as in the screens.

**Back up both the database and `.security/auth.key`.** The regular database dump includes users and encrypted authenticator secrets but does not include this key. Keep a separate secure copy of the key, preferably apart from database backups. The distribution ZIP excludes `.env`, `.venv`, backups and `.security`; do not upload your key or secrets to this chat. Loss of the encryption key requires restoring the matching key; the application does not silently switch off verification. Recovery codes cannot decrypt a lost key. Restrict application files/backups using Windows permissions, use a password-protected Windows account, and consider drive encryption. Backups are not encrypted by this application.

When restoring, stop the app, restore into a new database as described below and restore its matching key into `.security/auth.key` before starting. In the restored database, run `DELETE FROM auth_sessions; DELETE FROM auth_challenges; DELETE FROM auth_limits;` to invalidate restored sessions/challenges and old throttling state. Use fresh verification to sign in; test recovery and backup procedures before relying on them. The local owner recovery helper is for account/phone recovery, not encryption-key replacement.

This remains a single-PC, loopback HTTP deployment. Do not expose it to the LAN/internet; network deployment needs HTTPS, Secure cookies and a deployment/security review. Activity history records actions, table/record IDs and actor email, not before/after field values; local database administrators can alter it. Passkeys, email recovery, custom role permissions, automatic encrypted/key backups, owner authenticator replacement within the account screen and an independent security audit are future work. For owner phone replacement use recovery/local owner recovery; other owners can also reset that account.

Security references: [OWASP password storage](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html), [OWASP multifactor authentication](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html).

## Click a stock alert to open its product

Click the Critical, Warning, Notice or Out of stock badge beside a product (or its linked product name) to open its stock details and batches. Click **Add stock** in those details to open Inventory with the correct batch selected, or manage that product's stock levels directly. Summary count buttons open the product immediately when exactly one product matches; with multiple or zero matches they open the filtered Stock alerts list. Use **Show all alerts** to clear the priority filter. The filter is retained across the 30-second alert refresh. This is a frontend-only update: press Ctrl+F5 to load it; no database migration or restart is required.



## Choose the unit directly while adding stock

Restart `Start-TileStock.bat`, then press Ctrl+F5 in the browser. In **Inventory → Receive or adjust stock**, select the batch, enter a quantity, choose **Unit** (such as piece or box), enter a reason and save. There are no conversion factors, conversion setup panels or separate unit-change forms.

Saving the receipt also saves the product's unit for all its batches. Quantities, selling prices and low-stock threshold numbers are not converted or rescaled. Example: existing quantity 20, select box and receive 5; the resulting inventory is 25 box. Enter the numbers as you want to track them in the selected unit. A failed receipt rolls back both the unit change and the stock change. Retries do not add stock twice. A receipt based on an older unit label is rejected if another session has since changed it, so refresh and review the selected unit.

Saved invoice/estimate line units and previously recorded movement unit snapshots remain as originally recorded. New transactions use the updated product unit. This is a direct unit-label change, including for products with history, as requested; it does not reinterpret old transaction quantities. Previous conversion settings/records, if any, are retained in the database for audit only; conversion-write endpoints and controls have been removed, and requests attempting to use a conversion are rejected. Backups preserve this older history.

## Find existing batches

Open **Products & batches** to see **Saved batches** at the top of the page. Search by product name, SKU, batch name, colour, shade or size. The list shows the saved batch code, colour and available stock. Click a row's **Add stock** button to open Inventory with that exact batch selected; nothing is added until you enter a quantity/reason and save. The **Add batch** form below is for creating a new batch, not viewing existing ones. Batches are also listed under **Inventory → Stock by batch**. Press Ctrl+F5 after installing this display update; no database migration or restart is required for this frontend-only change.

## Search customers while creating invoices and estimates — new

Restart `Start-TileStock.bat` after stopping the app with Ctrl+C, then refresh the browser with Ctrl+F5. The local source is updated. This feature needs no new dependencies or database migration. When updating another installation, use the latest ZIP's source while keeping your existing `.env`, `.venv` and business database.

In **Invoices & payments → New invoice**, or **Estimates → New estimate**, type part of the customer's name or mobile number in **Customer — search by name or mobile number**. Name matching is case-insensitive and can match any part of the name. Mobile search ignores spaces, hyphens, brackets and the plus sign: typing `9876543210` also finds a saved number such as `+91 98765-43210`. Partial mobile numbers work too.

Select a matching result with the mouse/touch, or use Up/Down and Enter. Results include the name, saved phone number, address and customer ID to distinguish customers with the same name. Editing the search text clears the old selection; you must choose a result again before saving. Typing a name by itself does not create or select a customer. If no match exists, add the customer on the Customers page first. Escape closes the results.

The picker searches PostgreSQL after a short typing pause and shows up to 20 matches. If there are more, type more characters to narrow the list. Older pending searches are cancelled/ignored so they do not overwrite newer results. Search does not alter customer records, invoices or stock. It runs locally with no internet dependency. The rest of the starter still loads customer records for its existing Customers screen; large-scale customer-management pagination and search-performance benchmarking remain future work.



## Low-stock alerts by criticality — new

**Enable the update:** make a database backup, stop the application console with Ctrl+C, and start `Start-TileStock.bat` again. Press Ctrl+F5 in the browser. The local source files are already updated; the additive `004_stock_alerts.sql` migration runs on startup. Your `.env`, database connection and business records are preserved. When updating a different installation from the ZIP, replace the source while keeping `.env`, `.venv` and backups.

Use **Stock alerts → Set product stock levels** to configure an existing product. Choose High, Medium or Low product criticality, enter Minimum stock and Critical stock in that product's stock unit, leave Enable stock alerts checked, and save. You can also set these fields while adding a new product. Stock-policy edits change only the alert settings, not product identity, price, stock quantities or saved invoices.

Example: minimum 10 boxes, critical level 3 boxes. Stock of 11 is healthy. Stock of 10 through 3.001 produces the priority-dependent alert below; stock of 3 or less is Critical, except zero which is Out of stock. Thresholds include equality. Fractional levels up to three decimals are supported. Critical stock must be nonnegative and must not exceed minimum stock.

| Available sellable stock | Alert |
|---|---|
| Zero, with alerts enabled | Out of stock (highest urgency) |
| Positive, at/below a nonzero critical level | Critical for every product |
| Above critical level, at/below minimum; High product criticality | Critical |
| Above critical level, at/below minimum; Medium product criticality | Warning |
| Above critical level, at/below minimum; Low product criticality | Notice |
| Above minimum | Healthy |
| Alerts disabled | Disabled; no alerts, including for zero stock |

Availability is the sum of each product's sellable stock across all its batches, in its stock unit. Products with no batches have zero stock. Different units/products are never summed into one quantity. These alerts do not guarantee enough stock in a particular colour/shade/batch for a customer's order; invoice posting still checks the selected batch separately.

The dashboard and Inventory page show up to six most urgent alerts. The Stock alerts page shows the full list, per-severity counts and all product stock levels, including healthy/disabled products. Alert priority is Out of stock, Critical, Warning, Notice; ties use High/Medium/Low product criticality, then lowest stock as a proportion of minimum, then name/ID. Colours also have text labels. The menu shows the active product-alert count.

Alerts recalculate from committed stock after sales, voids, receipts, adjustments and returns. Damaged/non-restocked returns do not increase availability. Estimates/drafts do not reserve or reduce stock. Policy saves immediately refresh the alerts. The browser checks alerts every 30 seconds while visible and when you return to a hidden tab; this updates badges/tables without clearing unfinished form inputs. Normal app operations and the Refresh button also reload the data. A missed refresh reports an error; there is no background job when the app is closed.

Existing products default to Medium criticality, Minimum 0, Critical 0, alerts enabled. This flags out-of-stock products immediately without guessing appropriate positive reorder quantities for your business. Set nonzero quantities for products needing early warnings. A zero minimum monitors only out-of-stock status. Alerts can be disabled for products you intentionally do not stock.

This feature provides in-app alerts. Email/SMS/WhatsApp/desktop push notifications, supplier lead-time calculations, automatic purchase orders, per-batch thresholds, demand forecasting and automatic replenishment quantities are future work. Backups include product alert settings automatically.

## Customer returns and refunds — new

**Upgrade:** back up your database, close the application console with Ctrl+C, then start `Start-TileStock.bat` again. The local source files are already updated. Startup applies the additive `003_customer_returns.sql` migration. Refresh the browser with Ctrl+F5. For an installation copied from the ZIP, replace the source while keeping your existing `.env`, `.venv` and backups. Run setup if dependencies have not yet been installed. The update does not import demo data or replace your database.

### Receive goods back

1. Open **Customer returns** from the left menu (or open a posted invoice and choose **Receive customer return**).
2. Select the original posted invoice and click **Load invoice items**. Drafts, estimates and void invoices cannot receive returns.
3. Enter the quantity physically received for each item. Leave other lines at zero. The page shows quantities sold and previously returned; the server blocks quantities exceeding the remaining sale.
4. Keep **Resellable** checked to add that quantity to the original batch's available stock. Uncheck it for damaged/non-resellable goods: the return still receives monetary credit but does not add sellable inventory. If one item has both damaged and resellable quantities, save them as two separate return records with appropriate reasons.
5. Enter the reason and click **Receive return & update stock**. Saving is immediate. Owners may reverse incorrect records with a reason; check quantities before saving. The return appears in history with a `RET-` number and its stock movements reference the original invoice and return.

Do not also make a manual stock adjustment for these same goods. Stock, return history and credit commit together; a failure rolls back the entire return. UUID retries prevent the same submitted request being recorded twice. Starting a new form is a new request, so check history after an interrupted connection before re-entering quantities. Previously recorded manual return adjustments are not automatically detected or converted; do not enter those goods again without reconciling them first.

### Customer balance and refund

Return credit uses the original invoice selling price and cumulative half-up rounding. Full returns credit exactly the original rounded line amount. Small fractional partial returns can have zero monetary credit while still returning stock. The original invoice total/lines/payments are preserved; net sales and amount due reflect returns.

- **Unpaid invoice:** return credit reduces the amount the customer owes. There is no cash refund when no excess payment exists.
- **Partly paid invoice:** credit first reduces the unpaid amount. Any remaining credit becomes available for refund.
- **Fully paid invoice:** return credit becomes an amount owed back to the customer.

Open the original invoice. Its **Returns & refunds** section shows return credit, net invoice, refunds paid, amount due and remaining customer credit/refund due. Enter the amount actually refunded, method and reference, then click **Save refund record**. This records money already handed back; it does not transfer funds. Refunds cannot exceed the available credit, including when concurrent requests arrive. Recording a refund does not add stock again. Additional payments cannot exceed the invoice's remaining net amount due.

Example: sell five boxes at 10 each, collect 50, receive two resellable boxes. Stock increases by two; net invoice becomes 30 and customer credit is 20. After refunding and recording 20, the invoice balance is zero.

Balance formula: **original total - return credits - payments + refunds paid**. A positive balance is due from the customer; a negative balance is credit owed to the customer. Credits stay attached to their original invoice; automatically applying them to a different invoice is future work. Dashboard outstanding shows positive amounts due; invoice details show refund credit separately. Earlier signed balances, including return credits, contribute to the printed bill's previous balance. Bill PDFs show return credit, refunded total and net invoice in the footer without changing the original item lines.

Original return/refund records are retained, with owner-approved reversals available as described above. Invoices with active returns cannot be voided. Replacements/exchanges, unlinked returns, separate damaged-stock inventory, customer opening balances and statutory tax credit-note PDFs remain future work. Return detail/history is available onscreen; this update does not add a separate printable return-note document. Backups include the new return/refund tables automatically.

## Shivam Tiles bill layout update

The invoice PDF now follows the supplied sanitaryware bill: the same 594.75 × 432 point paper size, black borders, eight item columns, compact type, vehicle and payment fields, amount in words, carried totals and balances. Both estimates and invoices print **ESTIMATE SANITARYWARE**, as requested; their internal document types and stock behavior are unchanged. Draft/void status and document numbers remain visible. On Windows the template uses the installed Verdana and Times New Roman fonts; other systems fall back to standard PDF fonts. No font files are redistributed.

**Existing installation:** stop the app, make a database backup, keep your existing `.env`, and replace the application source files from the updated ZIP. Run `Setup-Windows.bat` again to install the new PDF dependency, then `Start-TileStock.bat`. Startup applies the additive `002_bill_layout.sql` migration without dropping existing records. If using the folder supplied in this chat, the source files have already been updated; rerun setup and restart. Do not replace your existing `.env` or database with sample settings/data.

Add Brand, Pack and Grade when creating a product; add Colour when creating a batch. Add Vehicle No. and Notes / Remark when creating a document. These fields are snapshotted with invoice lines and copied when converting estimates. Existing lines retain their previous product names; newly added fields on older records remain blank. Editing already-saved product/document details is not added by this update.

Open a document to see its PDF preview, then click **Open / Print bill PDF**. Print from the PDF viewer at **Actual size / 100%**; select a matching custom paper size for the closest physical match. Printing scaled to A4 changes the dimensions. Browser PDF previews depend on browser support; the separate PDF button provides the same generated file.

Cash Rs sums cash payments; Bill Amt Rs sums bank/card/UPI/other payments, as confirmed for this application. Previous Balance Rs is the current unpaid balance of this customer's earlier posted invoices (earlier document IDs), calculated when the PDF is opened. Current Balance Rs adds this document's net balance after returns and refunds; void documents contribute zero. These are live balances, not historical account statement balances or a separate customer opening-balance ledger. Payments made later can change reprinted balances. An estimate's current balance is a projected figure, since estimates do not create receivables. Amount in words spells out the document total using the reference's international number wording and includes paise when applicable. Long rows wrap; multi-page bills carry cumulative amounts and quantities. Long remarks/addresses continue on attached details pages so text is preserved.

The sample preview uses the supplied bill's 24 lines to demonstrate pagination and totals; it is not imported into your database. PDF rendering does not change inventory, posting or payment transactions. No tax calculation was added.

A usable single-PC tile inventory and billing starter. FastAPI serves a plain browser interface and stores business data in PostgreSQL on your PC. No Node.js, Docker, paid services or frontend build step. Internet is needed for the first Python dependency installation; normal use works offline.

**Start here:** extract the ZIP, read steps 1–5 below, then double-click `Start-TileStock.bat`. Do not run from inside the ZIP.

## What is implemented

- Product catalogue: SKU, name, stock unit, informational area per unit and selling price.
- Batches: lot code, shade, size, separate quantities for each batch.
- Opening stock, receipts and signed adjustments with mandatory reasons and a movement ledger.
- Customers with phone/address; customer name and address are snapshotted on documents.
- Draft estimates and invoices with multiple batch lines and decimal line totals; owners can correct drafts with a reason.
- Convert an estimate into one invoice draft; repeated conversion returns that same invoice.
- Post invoices to deduct stock atomically; insufficient stock rolls back the entire posting.
- Row locks serialize competing sales, stock adjustments, payments and cancellations. Negative stock and overpayments are blocked. Posting and voiding can be retried safely.
- Partial/full payments against posted invoices, with method, reference, balance and payment history.
- UUID retry keys for document creation, stock adjustments and payments. Same key/body returns the original result; changed data with the same key is rejected.
- Void drafts and unpaid posted invoices. Voiding a posted invoice restores stock once. Invoices with payments or active returns cannot be voided; use the return workflow for goods received back.
- Overview, stock search, recent movement ledger, document detail, browser printing / Save as PDF.
- Ordered, transactional SQL migrations, Windows setup/start/backup helpers and two-copy backup rotation.

## Explicit boundaries / future work

This is a starter for one trusted local Windows account, not a full accounting or statutory invoicing system. **No GST/VAT/tax calculation or compliant tax invoice format** is implemented. Prices are used as entered, without taxes, discounts, shipping or currency conversion. Currency is a display label; the database does not support multiple currencies.

Future work: passkeys, email recovery, custom permissions, network or multi-device deployment, statutory tax invoices and numbering rules, statutory tax credit notes, cross-invoice store-credit transfers, suppliers and purchase orders, barcode scanning, expenses/profit reports, spreadsheet import/export, automatic stock allocation, reservations, sales-document unit conversions, automatic scheduled backups, direct Google Drive API uploads, encryption and disaster recovery automation.

The page loads catalogues/documents in memory; the ledger displays the latest 500 movements. Pagination and very large catalogue optimization are future work. Document numbers use database IDs (`INV-000123`); gaps are normal and numbers are not financial-year sequences. Master records/documents are not hard-deleted through the app. Owners may edit a draft with a reason; posted and void documents retain their saved details. A converted estimate stays visible; voiding it does not cancel its linked invoice.

## Requirements for an 8 GB RAM PC

- 64-bit Windows 10 or 11, a current Edge/Chrome/Firefox browser.
- Python **3.12, 64-bit**, including the Python launcher (`py`). Download from [python.org](https://www.python.org/downloads/windows/). During installation select **Install launcher** and **Add python.exe to PATH**.
- PostgreSQL already installed and its Windows service running. PostgreSQL 18 was used for this package's live tests; other major versions were not tested.
- Your PostgreSQL administrator password (the one chosen during PostgreSQL installation).

The launcher runs one server worker with no reload process. Each API request uses a short-lived database connection. There are no background workers or heavyweight frontend tools. No fixed RAM/performance benchmark is claimed. Keep PostgreSQL's installer defaults initially and close unnecessary applications. Do not uninstall/reinstall your existing PostgreSQL.

## Windows installation — step by step

### 1. Extract the application

Right-click `TileStock-Pro.zip` → **Extract All**. Move the extracted `TileStock-Pro` folder somewhere you own, for example `C:\TileStock-Pro` (if writable) or your Documents folder. Avoid `Program Files`, a network share and a cloud-synced application/database folder. You can create a desktop shortcut to `Start-TileStock.bat` later.

### 2. Create a dedicated database and login

Open **pgAdmin**, connect to your local PostgreSQL server as `postgres`, and open **Query Tool** for the existing `postgres` database.

Run this statement, replacing the sample password with your own strong password:

```sql
CREATE ROLE tilestock_app LOGIN PASSWORD 'REPLACE_WITH_YOUR_PASSWORD';
```

Then run this statement **separately**, with pgAdmin auto-commit enabled (not inside `BEGIN` / a transaction):

```sql
CREATE DATABASE tilestock OWNER tilestock_app;
```

If either name already exists, inspect it first. Do not drop or overwrite an existing database. Choose a new name and use it in `.env` instead. The application login owns only its dedicated database and should not be a PostgreSQL superuser.

### 3. Install application dependencies

Double-click **Setup-Windows.bat**. A console window installs the pinned Python packages into a local `.venv` folder. Initial installation needs internet. No administrator privileges are normally needed. If Windows displays a downloaded-file warning, review the included source before allowing it.

The setup helper also copies `.env.example` to `.env` if `.env` does not yet exist. It never replaces an existing `.env`.

### 4. Configure the database connection

Enable **View → Show → File name extensions** in Explorer. Open `.env` in Notepad and change this line:

```dotenv
DATABASE_URL=postgresql://tilestock_app:YOUR_PASSWORD@127.0.0.1:5432/tilestock
```

Use your own password, database and installed port (usually `5432`). URL-encode special password characters: `@` → `%40`, `#` → `%23`, `%` → `%25`, `:` → `%3A`, `/` → `%2F`, `?` → `%3F`. Do not include literal angle-bracket placeholders or surround the whole URL in angle brackets. Keep `.env` private; do not share it in screenshots, email or source control.

Set `BUSINESS_NAME` and `CURRENCY` as desired. Use `INR` for rupees. `PG_BIN` is used only for backups: change `18` to your installed PostgreSQL version. Leave `CLOUD_BACKUP_DIR` blank for now. Save as `.env`, not `.env.txt`.

### 5. Create the owner and start Shivam Tiles

Run **Setup-Owner.bat** first to choose the owner email/password. Then double-click **Start-TileStock.bat**. Sign in, enrol your authenticator and save recovery codes as described at the top of this README. Startup initializes the schema automatically in the dedicated database and opens [Shivam Tiles on this PC](http://127.0.0.1:8000).

Keep the console window open while using the app. Stop with **Ctrl+C** in that window. Start it again whenever needed; all business records remain in PostgreSQL. Closing a browser tab alone does not stop the server. If the browser does not open automatically, open the address above manually after the console says startup is complete.

This package does not install a Windows service or start on login. It binds only to `127.0.0.1`. Keep that setting: email/password and authenticator verification protect application access. Other applications/users on your local PC with access to the app or database may access business records. Do not expose port 8000 through a router or change the binding to `0.0.0.0`. Host/origin checks also reject common cross-site write attempts. Windows administrators, database administrators and anyone able to read the application files/database remain trusted; application roles cannot protect against those privileges.

## First sale walkthrough

1. **Products & batches:** add SKU `TILE-001`, name `Ivory 600 × 600`, unit `box`, area per unit `1.44`, price `800.00`. Area is informational; quantities/prices use boxes.
2. Add a batch for that product with code `LOT-01`, shade `A`, size `600 × 600`.
3. **Inventory:** choose that batch, enter quantity change `10` and reason `Opening stock`. Available stock becomes 10 boxes. Enter `-1` only when intentionally reducing stock (damage/correction).
4. **Customers:** add a customer.
5. **Estimates:** select the customer, choose the batch, quantity `3`, unit price `800.00`, and save. Stock remains 10. Open the estimate and choose **Create invoice draft**.
6. In the invoice detail, choose **Post invoice & deduct stock**. Stock becomes 7. A second posting does not deduct again. Drafts and estimates do not reserve stock, so a later posting can fail if another sale used it.
7. Record a payment of `1000.00`. The balance becomes `1400.00`. Record the remaining balance when received. Payment timestamps are recording times; backdating is not implemented.
8. Use **Print / Save PDF** for a document copy. Draft/void status is printed. This starter does not generate a compliant tax invoice.

A free-of-charge invoice (zero prices) is supported and still deducts stock when posted. Each batch may appear once per document; combine quantities or select a different batch. Fractional stock is supported to three decimals, including for `box`; use whole boxes if that is your business rule.

Monetary inputs accept at most two decimals; each `quantity × price` line is rounded half-up to two decimals and totals sum those rounded lines. The browser total is a preview; PostgreSQL/server-calculated totals are authoritative. All invoice lines, movements and posting status commit together or roll back together. Payments lock the invoice row before checking outstanding balance. Retry keys protect a retried operation in the same form; a brand-new form/new key represents a new operation. Review existing records after a network failure before starting a new form.

## Backup — two local copies and two Google Drive copies

The database is **not** stored in this application folder. Copying just the ZIP/app folder does not back up sales or stock.

1. Set `PG_BIN` in `.env` to the bin directory containing `pg_dump.exe` and `pg_restore.exe`, for example `C:\Program Files\PostgreSQL\18\bin`. Use the same major version as the server, or a newer compatible client.
2. For Google Drive, install and sign into **Google Drive for desktop** yourself. Create a dedicated synced folder such as `G:\My Drive\TileStock Backups`. Confirm that it exists in Explorer and sync works.
3. Put the actual folder path into `.env`:

   ```dotenv
   CLOUD_BACKUP_DIR="G:\My Drive\TileStock Backups"
   ```

4. Double-click **Backup-Windows.bat** after each working day or important import. It makes a consistent custom-format dump, verifies that `pg_restore` can read its archive listing, and copies it to the configured synced folder. It compares file checksums before rotating copies. A listing/checksum check is not a full restore test.
5. The helper keeps the **two newest** timestamped `tilestock_*.dump` files in its local `backups` folder and the **two newest** in that dedicated synced folder. It rotates only after dump validation and any configured copy succeed. Failed runs keep previous copies; a `.partial` file may remain and can be removed after investigating. Arbitrary files/subdirectories are not deleted. Do not put backups from different databases/installations in the same folder.
6. **Check the Drive sync icon and Drive website yourself.** The helper confirms a filesystem copy, not an uploaded cloud object. Uploads and deletions are eventually handled by Drive for desktop. Offline files may not be in the cloud yet; deleted cloud items can remain in Drive Trash/version history. It cannot guarantee exactly two cloud objects at every instant or permanent cloud deletion. Direct Drive API confirmation/retention is future work.

Backups are not encrypted by this application. Protect the local/synced folders and Google account. Retaining only two copies gives a short recovery window; consider occasional separate offline copies. Do not sync PostgreSQL's live data directory. Save `.env` securely and keep a copy of this application ZIP separately. There is no scheduled task installed; run backups manually or configure Windows Task Scheduler to run `.venv\Scripts\python.exe backup.py` with **Start in** set to the application folder and an account that can access the synced drive. Test the scheduled job yourself.

### Restore safely into a NEW database

Periodically test a restore. Stop the app before switching its database. Never restore over your only working database.

1. In pgAdmin, create a new empty database owned by `tilestock_app` (run separately):

   ```sql
   CREATE DATABASE tilestock_restore OWNER tilestock_app;
   ```

2. Open PowerShell. Replace the PostgreSQL path and backup filename, then run this command. `-W` prompts for the database password:

   ```powershell
   & 'C:\Program Files\PostgreSQL\18\bin\pg_restore.exe' -h 127.0.0.1 -p 5432 -U tilestock_app -W --dbname tilestock_restore --no-owner --no-privileges --single-transaction --exit-on-error 'C:\TileStock-Pro\backups\YOUR_BACKUP.dump'
   ```

3. After successful restoration, save your original `.env` securely and change its database name to `tilestock_restore`. Start the app and check product quantities, documents, totals and balances. The restored `schema_migrations` table prevents reapplying the initial migration.
4. Keep the original database until you have verified recovery. To return to it, stop the app and restore the original database name in `.env`. A PostgreSQL dump does not include server roles; create the login/owner first on a replacement PC.

## Troubleshooting

- **`py` not recognized / Python missing:** install Python 3.12 with the launcher and rerun setup.
- **Package download error:** check internet/proxy/firewall, then rerun setup. Existing database records are unaffected.
- **Connection refused:** open Windows Services and start your PostgreSQL service. Verify host and port in `.env`.
- **Password authentication failed:** check the database login/password and URL escaping. Your pgAdmin master password is different from your PostgreSQL role password.
- **Database does not exist / permission denied:** create the dedicated database owned by `tilestock_app` as in step 2. Do not use someone else's existing database.
- **`.env` missing:** copy `.env.example`, enable filename extensions and avoid `.env.txt`.
- **Port 8000 already in use:** stop an existing app console with Ctrl+C or close the other service using that port. The launcher deliberately refuses to start a second instance.
- **Insufficient stock:** receive stock or void/recreate the draft with a lower quantity or correct batch. There is no automatic substitution of batches.
- **Database busy:** a lock times out after 10 seconds, statements after 30 seconds. Retry the same operation after the competing request completes. Check the console for database errors.
- **Paid invoice cannot be voided:** use Customer returns for received goods and record any money refunded on the invoice; do not manually delete payments.
- **Backup failed:** check database access, PostgreSQL client version/path, writable space and synced-folder availability. Older backups are retained if creation/copy fails.

## Source layout and developer use

```text
app/main.py          FastAPI routes, transactions and local request checks
app/models.py        Input constraints and decimal rounding
app/db.py            Connections and ordered transactional migration runner
app/static/          Offline HTML, CSS, JavaScript frontend
migrations/          Versioned PostgreSQL SQL schema
tests/               Validation and real PostgreSQL integration tests
launcher.py          Local server + browser launcher
backup.py            Dump/copy/validate/rotate helper
```

To initialize without starting the web server: `.venv\Scripts\python.exe -m app.db`. Migrations also run automatically at startup. New migrations should have increasing filenames (`002_...sql`) and be added, not edited after installation. Back up before upgrades. There are no automatic down migrations. API docs are available at `http://127.0.0.1:8000/docs`; for write operations in an API client include `X-TileStock-Client: local` (the bundled Swagger UI does not add it for you).

Validation-only tests (integration tests skip without a test URL):

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-test.txt
.venv\Scripts\python.exe -m pytest -q
```

Real database tests **truncate their target tables**. Create a completely separate disposable database and never use your shop URL:

```powershell
$env:TILESTOCK_TEST_DATABASE_URL='postgresql://TEST_USER:TEST_PASSWORD@127.0.0.1:5432/tilestock_test'
.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TILESTOCK_TEST_DATABASE_URL
```

See `TESTING.md` for the checks actually performed on this delivered version, including any limitations. No credentials, existing shop data or Python virtual environment are included in the ZIP.
