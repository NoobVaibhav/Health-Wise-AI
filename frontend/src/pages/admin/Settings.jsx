import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { createDepartment, listDepartments } from "../../services/adminApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import { Button, Input } from "../../components/ui";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function Settings() {
  const { data, loading, error, reload } = useFetch(listDepartments);
  const [name, setName] = useState("");
  const [problem, setProblem] = useState("");
  const add = async (e) => {
    e.preventDefault();
    setProblem("");
    try { await createDepartment(name); setName(""); reload(); } catch (err) { setProblem(getErrorMessage(err)); }
  };
  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <PageTitle title="Settings" subtitle="Hospital departments" />
      <Section title="Departments">
        {loading ? <Loading /> : error ? <ErrorBox message={error} /> : (
          <ul className="mb-4 divide-y">{data.length === 0 && <li className="py-2 text-slate-500">No departments yet.</li>}{data.map((d) => <li key={d.id} className="py-2">{d.name}</li>)}</ul>
        )}
        <form onSubmit={add} className="flex gap-2"><Input placeholder="New department name" required value={name} onChange={(e) => setName(e.target.value)} /><Button>Add</Button></form>
        {problem && <p className="mt-2 text-sm text-red-600">{problem}</p>}
      </Section>
    </div>
  );
}
