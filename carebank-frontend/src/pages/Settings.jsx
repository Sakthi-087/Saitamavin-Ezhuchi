import { useState } from 'react'
import { SectionCard } from '../components/Cards'
import StatusBadge from '../components/ui/StatusBadge'

function ToggleRow({ title, description, enabled, onToggle, disabled }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      className="flex w-full items-center justify-between gap-4 rounded-[22px] border border-slate-200/80 bg-white p-4 text-left shadow-sm transition hover:border-slate-300 disabled:cursor-not-allowed disabled:opacity-70"
    >
      <div>
        <p className="font-semibold text-slate-900">{title}</p>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <div className={`flex h-7 w-12 items-center rounded-full px-1 ${enabled ? 'justify-end bg-emerald-500' : 'justify-start bg-slate-300'}`}>
        <span className="h-5 w-5 rounded-full bg-white shadow-sm" />
      </div>
    </button>
  )
}

export default function Settings({
  uploading,
  manualSaving,
  uploadState,
  fraudCheck,
  onUpload,
  onManualCreate,
  preferences,
  preferencesSaving,
  onTogglePreference,
}) {
  const [file, setFile] = useState(null)
  const [manualForm, setManualForm] = useState({
    date: new Date().toISOString().slice(0, 10),
    description: '',
    amount: '',
    category: 'Food',
  })

  function handleSubmit(event) {
    event.preventDefault()
    if (!file) return
    onUpload(file)
  }

  function handleManualChange(event) {
    const { name, value } = event.target
    setManualForm((current) => ({
      ...current,
      [name]: value,
    }))
  }

  async function handleManualSubmit(event) {
    event.preventDefault()
    const trimmedDescription = manualForm.description.trim()
    if (!trimmedDescription || !manualForm.amount || !manualForm.date || !manualForm.category) return

    await onManualCreate({
      ...manualForm,
      description: trimmedDescription,
      amount: Number(manualForm.amount),
    })

    setManualForm((current) => ({
      ...current,
      description: '',
      amount: '',
    }))
  }

  return (
    <div className="space-y-6">
      <SectionCard
        title="Data Controls"
        subtitle="Manage transaction ingestion, manual entry, and notification preferences without leaving the intelligence workspace."
        action={<StatusBadge label="Workspace controls" tone="info" />}
      >
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[24px] border border-slate-200/80 bg-slate-950 p-5 text-white shadow-[0_20px_45px_rgba(15,23,42,0.16)]">
            <p className="text-xs uppercase tracking-[0.22em] text-cyan-200">Import pipeline</p>
            <p className="mt-3 text-2xl font-semibold">CSV or manual</p>
            <p className="mt-2 text-sm leading-6 text-slate-200">Bring statements into the scoring and alert pipeline.</p>
          </div>
          <div className="rounded-[24px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Current alerts</p>
            <p className="mt-3 text-3xl font-semibold text-slate-950">{fraudCheck?.flagged_transactions?.length || 0}</p>
            <p className="mt-2 text-sm text-slate-500">Transactions currently flagged for review.</p>
          </div>
          <div className="rounded-[24px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <p className="text-xs uppercase tracking-[0.22em] text-slate-500">Preferences</p>
            <p className="mt-3 text-3xl font-semibold text-slate-950">{Object.values(preferences || {}).filter(Boolean).length}</p>
            <p className="mt-2 text-sm text-slate-500">Enabled workspace preferences.</p>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="Safety Snapshot" subtitle="Recent anomaly detections available for demo and review">
          {fraudCheck?.flagged_transactions?.length ? (
            <div className="space-y-3">
              {fraudCheck.flagged_transactions.slice(0, 3).map((item) => (
                <div key={`${item.description}-${item.amount}`} className="rounded-[22px] border border-slate-200/80 bg-slate-50/90 p-4 shadow-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-950">{item.description}</p>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${item.risk === 'High' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>{item.risk}</span>
                  </div>
                  <p className="mt-2 text-sm text-slate-500">Rs {Number(item.amount).toLocaleString('en-IN')}</p>
                  <p className="mt-2 text-sm text-slate-600">{item.flags.join(', ')}</p>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-[22px] border border-emerald-200/80 bg-emerald-50 p-5 text-sm text-emerald-800">
              No suspicious transactions are currently flagged.
            </div>
          )}
      </SectionCard>

      <SectionCard title="Transaction Ingestion" subtitle="Upload a statement or add a single transaction manually into the CareBank pipeline">
        <div className="grid gap-6 xl:grid-cols-2">
          <form onSubmit={handleSubmit} className="space-y-4 rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <div>
              <p className="font-semibold text-slate-900">CSV import</p>
              <p className="mt-1 text-sm text-slate-500">Upload a bank or wallet export when you want to sync many rows at once.</p>
            </div>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(event) => setFile(event.target.files?.[0] || null)}
              className="block w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700"
            />
            <button
              type="submit"
              disabled={!file || uploading}
              className="rounded-[18px] bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-900 disabled:opacity-60"
            >
              {uploading ? 'Uploading...' : 'Upload CSV'}
            </button>
          </form>

          <form onSubmit={handleManualSubmit} className="space-y-4 rounded-[28px] border border-slate-200/80 bg-white p-5 shadow-sm">
            <div>
              <p className="font-semibold text-slate-900">Manual entry</p>
              <p className="mt-1 text-sm text-slate-500">Capture a recent cash payment, income event, or one-off spend without preparing a CSV.</p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="space-y-2 text-sm text-slate-600">
                <span>Date</span>
                <input
                  type="date"
                  name="date"
                  value={manualForm.date}
                  onChange={handleManualChange}
                  className="block w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700"
                />
              </label>
              <label className="space-y-2 text-sm text-slate-600">
                <span>Category</span>
                <select
                  name="category"
                  value={manualForm.category}
                  onChange={handleManualChange}
                  className="block w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700"
                >
                  <option value="Food">Food</option>
                  <option value="Shopping">Shopping</option>
                  <option value="Travel">Travel</option>
                  <option value="Bills">Bills</option>
                  <option value="Income">Income</option>
                  <option value="Uncategorized">Uncategorized</option>
                </select>
              </label>
            </div>
            <label className="block space-y-2 text-sm text-slate-600">
              <span>Description</span>
              <input
                type="text"
                name="description"
                value={manualForm.description}
                onChange={handleManualChange}
                placeholder="Example: Pharmacy, Salary, Rent"
                className="block w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700"
              />
            </label>
            <label className="block space-y-2 text-sm text-slate-600">
              <span>Amount (Rs)</span>
              <input
                type="number"
                name="amount"
                min="0.01"
                step="0.01"
                value={manualForm.amount}
                onChange={handleManualChange}
                placeholder="0.00"
                className="block w-full rounded-[18px] border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700"
              />
            </label>
            <button
              type="submit"
              disabled={manualSaving || !manualForm.date || !manualForm.description.trim() || !manualForm.amount}
              className="rounded-[18px] bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:opacity-60"
            >
              {manualSaving ? 'Saving...' : 'Add Transaction'}
            </button>
          </form>
        </div>

        {uploadState ? (
          <div className={`mt-4 rounded-[22px] border p-4 text-sm shadow-sm ${uploadState.tone === 'success' ? 'border-emerald-200 bg-emerald-50 text-emerald-700' : 'border-rose-200 bg-rose-50 text-rose-700'}`}>
            <p className="font-semibold">{uploadState.message}</p>
            {uploadState.errors?.length ? (
              <div className="mt-3 space-y-1">
                {uploadState.errors.slice(0, 5).map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </div>
            ) : null}
            {uploadState.fraudSummary?.length ? (
              <div className="mt-4 rounded-[22px] border border-amber-200/80 bg-amber-50 p-4 text-amber-900">
                <p className="font-semibold">Suspicious transactions detected</p>
                <div className="mt-3 space-y-2">
                  {uploadState.fraudSummary.slice(0, 5).map((item) => (
                    <div key={`${item.description}-${item.amount}`} className="rounded-[18px] bg-white/70 px-3 py-2">
                      <p className="font-medium">{item.description} - Rs {Number(item.amount).toLocaleString('en-IN')}</p>
                      <p className="text-xs uppercase tracking-wide">{item.risk} risk</p>
                      <p className="mt-1 text-xs">{item.flags.join(', ')}</p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        ) : null}
      </SectionCard>

      <SectionCard title="Notification Preferences" subtitle="Suggested operating defaults for the product">
        <div className="space-y-4">
          <ToggleRow
            title="Overspending alerts"
            description="Notify when a category exceeds its recommended range."
            enabled={preferences.overspending_alerts}
            onToggle={() => onTogglePreference('overspending_alerts')}
            disabled={preferencesSaving}
          />
          <ToggleRow
            title="Weekly wellness summary"
            description="Receive a weekly recap of health score, risks, and suggestions."
            enabled={preferences.weekly_wellness_summary}
            onToggle={() => onTogglePreference('weekly_wellness_summary')}
            disabled={preferencesSaving}
          />
          <ToggleRow
            title="AI assistant tips"
            description="Show proactive prompts when the assistant detects unusual spending patterns."
            enabled={preferences.ai_assistant_tips}
            onToggle={() => onTogglePreference('ai_assistant_tips')}
            disabled={preferencesSaving}
          />
          {preferencesSaving ? <p className="text-sm text-slate-500">Saving your preferences...</p> : null}
        </div>
      </SectionCard>
    </div>
  )
}
