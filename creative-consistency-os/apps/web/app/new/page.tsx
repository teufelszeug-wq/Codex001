"use client";

import { FormEvent, useState } from "react";
import { createProject } from "../../lib/api";

export default function NewProjectPage() {
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    try {
      const project = await createProject(title);
      setMessage(`作成しました: ${project.title}`);
      setTitle("");
    } catch {
      setMessage("作成できませんでした。APIが起動しているか確認してください。");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="shell narrow">
      <p className="eyebrow">NEW PROJECT</p>
      <h1>新しい作品を作る</h1>
      <p>M1では作品コンテナを作成します。ジャンル選択とWorld BuilderはM2でここに接続します。</p>
      <form className="form" onSubmit={submit}>
        <label htmlFor="title">作品名</label>
        <input id="title" maxLength={200} required value={title} onChange={(e) => setTitle(e.target.value)} />
        <button disabled={busy} type="submit">{busy ? "作成中…" : "作品を作成"}</button>
      </form>
      {message && <p className="notice">{message}</p>}
    </main>
  );
}
