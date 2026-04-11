'use client';

import Link from 'next/link';
import { forwardRef, useEffect, useImperativeHandle, useState } from 'react';
import { ArrowUpRight } from 'lucide-react';
import {
  coachingApiGroups,
  type CoachGroup,
  type CoachGroupDetail,
  type CoachingClient,
} from '@/lib/api/coaching';

const PANEL_CLASS = 'rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white';
const GROUP_COLORS = [
  { bg: '#EEEDFE', text: '#3C3489' },
  { bg: '#E1F5EE', text: '#085041' },
  { bg: '#FAEEDA', text: '#633806' },
  { bg: '#E6F1FB', text: '#185FA5' },
  { bg: '#FAECE7', text: '#712B13' },
];

export type GroupsTabHandle = {
  createGroup: (name: string) => Promise<void>;
};

type GroupsTabProps = {
  clients: CoachingClient[];
};

const GroupsTab = forwardRef<GroupsTabHandle, GroupsTabProps>(function GroupsTab({ clients }, ref) {
  const [groups, setGroups] = useState<CoachGroup[]>([]);
  const [detail, setDetail] = useState<CoachGroupDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [creating, setCreating] = useState(false);
  const [showAddMember, setShowAddMember] = useState(false);
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskText, setTaskText] = useState('');
  const [taskDue, setTaskDue] = useState('');
  const [addingTask, setAddingTask] = useState(false);
  const [selectedClientIds, setSelectedClientIds] = useState<string[]>([]);
  const [addingMembers, setAddingMembers] = useState(false);

  useEffect(() => {
    let isActive = true;

    const loadGroups = async () => {
      try {
        const result = await coachingApiGroups.getCoachGroups();
        if (!isActive) {
          return;
        }
        setGroups(result);
        if (result[0]) {
          await loadDetail(result[0].id, result[0]);
        } else {
          setLoading(false);
        }
      } catch {
        if (isActive) {
          setLoading(false);
        }
      }
    };

    void loadGroups();

    return () => {
      isActive = false;
    };
  }, []);

  async function loadDetail(groupId: string, summaryGroup?: CoachGroup) {
    if (summaryGroup) {
      setDetail((current) => (
        current && current.group.id === groupId
          ? { ...current, group: summaryGroup }
          : { group: summaryGroup, members: [], tasks: [] }
      ));
    }
    setDetailLoading(true);
    try {
      const result = await coachingApiGroups.getCoachGroupDetail(groupId);
      setDetail(result);
    } finally {
      setDetailLoading(false);
      setLoading(false);
    }
  }

  async function createGroup(name: string) {
    const normalizedName = name.trim();
    if (!normalizedName || creating) {
      return;
    }

    setCreating(true);
    try {
      const group = await coachingApiGroups.createCoachGroup(normalizedName);
      setGroups((current) => [...current, group]);
      await loadDetail(group.id, group);
    } finally {
      setCreating(false);
    }
  }

  useImperativeHandle(ref, () => ({
    createGroup,
  }));

  async function handleAddSelectedMembers() {
    if (!detail || selectedClientIds.length === 0) {
      return;
    }

    setAddingMembers(true);
    try {
      const members = await coachingApiGroups.addGroupMembers(detail.group.id, selectedClientIds);
      setDetail((current) => (
        current
          ? {
              ...current,
              members: [...current.members, ...members],
              group: { ...current.group, memberCount: current.group.memberCount + members.length },
            }
          : current
      ));
      setGroups((current) => current.map((group) => (
        group.id === detail.group.id
          ? { ...group, memberCount: group.memberCount + members.length }
          : group
      )));
      setSelectedClientIds([]);
      setShowAddMember(false);
    } finally {
      setAddingMembers(false);
    }
  }

  async function handleRemoveMember(clientId: string) {
    if (!detail) {
      return;
    }

    const previousDetail = detail;
    const previousGroups = groups;

    setDetail((current) => (
      current
        ? {
            ...current,
            members: current.members.filter((member) => member.clientId !== clientId),
            tasks: current.tasks.map((task) => ({
              ...task,
              totalCount: Math.max(task.totalCount - 1, 0),
              doneCount: task.doneCount,
            })),
            group: { ...current.group, memberCount: Math.max(current.group.memberCount - 1, 0) },
          }
        : current
    ));
    setGroups((current) => current.map((group) => (
      group.id === detail.group.id
        ? { ...group, memberCount: Math.max(group.memberCount - 1, 0) }
        : group
    )));

    try {
      await coachingApiGroups.removeGroupMember(detail.group.id, clientId);
      const nextGroup = {
        ...detail.group,
        memberCount: Math.max(detail.group.memberCount - 1, 0),
      };
      void loadDetail(detail.group.id, nextGroup);
    } catch {
      setDetail(previousDetail);
      setGroups(previousGroups);
    }
  }

  async function handleCreateTask() {
    if (!detail || !taskText.trim()) {
      return;
    }

    setAddingTask(true);
    try {
      const task = await coachingApiGroups.createGroupTask(detail.group.id, {
        text: taskText.trim(),
        dueDate: taskDue || null,
      });
      setDetail((current) => (
        current
          ? { ...current, tasks: [...current.tasks, task] }
          : current
      ));
      setTaskText('');
      setTaskDue('');
      setShowTaskForm(false);
    } finally {
      setAddingTask(false);
    }
  }

  async function handleDeleteTask(taskId: string) {
    if (!detail) {
      return;
    }

    await coachingApiGroups.deleteGroupTask(detail.group.id, taskId);
    setDetail((current) => (
      current
        ? { ...current, tasks: current.tasks.filter((task) => task.id !== taskId) }
        : current
    ));
  }

  const availableClients = detail
    ? clients.filter((client) => !detail.members.some((member) => member.clientId === client.id))
    : clients;

  function toggleSelectedClient(clientId: string) {
    setSelectedClientIds((current) => (
      current.includes(clientId)
        ? current.filter((id) => id !== clientId)
        : [...current, clientId]
    ));
  }

  if (loading) {
    return (
      <div className="grid animate-pulse gap-[14px] xl:grid-cols-[260px_minmax(0,1fr)]">
        <div className="h-64 rounded-[8px] bg-[#ece7dd]" />
        <div className="h-64 rounded-[8px] bg-[#ece7dd]" />
      </div>
    );
  }

  return (
    <div className="grid gap-[14px] xl:grid-cols-[260px_minmax(0,1fr)]">
      <div className={`${PANEL_CLASS} flex min-h-[420px] flex-col`}>
        <div className="border-b border-[#e0ddd6] px-[12px] py-[10px] text-[11px] font-medium uppercase tracking-[0.4px] text-[#73726c]">
          Группы
        </div>

        <div className="flex-1 overflow-y-auto p-[8px]">
                    {groups.length === 0 ? (
            <div className="flex min-h-[160px] items-center justify-center rounded-[8px] border-[0.5px] border-dashed border-[#e0ddd6] bg-[#fbfaf7] p-4 text-center">
              <div className="max-w-[220px] text-[#73726c]">
                <div className="flex justify-center">
                  <ArrowUpRight className="h-5 w-5 -translate-y-1 translate-x-8" />
                </div>
                <div className="text-[12px] leading-5">
                  Для добавления групп нажмите кнопку <span className="font-medium text-[#1a1a18]">&quot;+&quot;</span>
                </div>
              </div>
            </div>
          ) : (
            groups.map((group, index) => {
              const color = GROUP_COLORS[index % GROUP_COLORS.length];
              const isActive = detail?.group.id === group.id;
              return (
                <button
                  key={group.id}
                  type="button"
                  onClick={() => void loadDetail(group.id, group)}
                  className={`mb-[2px] flex w-full items-center gap-[8px] rounded-[8px] px-[10px] py-[8px] text-left transition-colors ${
                    isActive ? 'bg-[#e6f1fb]' : 'hover:bg-[#f5f4f0]'
                  }`}
                >
                  <div
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[8px] text-[11px] font-medium"
                    style={{ background: color.bg, color: color.text }}
                  >
                    {group.initials || group.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className={`truncate text-[12px] font-medium ${isActive ? 'text-[#185FA5]' : 'text-[#1a1a18]'}`}>
                      {group.name}
                    </div>
                    <div className={`text-[10px] ${isActive ? 'text-[#185FA5] opacity-70' : 'text-[#73726c]'}`}>
                      {group.memberCount} участн.
                    </div>
                  </div>
                </button>
              );
            })
          )}
        </div>
      </div>

      <div className={`${PANEL_CLASS} min-w-0`}>
        {!detail ? (
          <div className="flex min-h-[420px] items-center justify-center text-[13px] text-[#73726c]">
            Выберите группу слева
          </div>
        ) : (
          <>
            <div className="flex items-center justify-between border-b border-[#e0ddd6] px-[14px] py-[12px]">
              <div>
                <div className="text-[13px] font-medium text-[#1a1a18]">{detail.group.name}</div>
                <div className="text-[11px] text-[#73726c]">
                  {detail.group.memberCount} участников · {detailLoading ? 'загрузка...' : `${detail.tasks.length} заданий`}
                </div>
              </div>
              <div className="flex gap-[6px]">
                <button
                  type="button"
                  onClick={() => {
                    setShowAddMember((current) => !current);
                    setShowTaskForm(false);
                    setSelectedClientIds([]);
                  }}
                  className="rounded-[6px] border-[0.5px] border-[#d3d1c7] px-3 py-[5px] text-[11px] text-[#73726c] transition-colors hover:bg-[#f5f4f0]"
                >
                  + Участник
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowTaskForm((current) => !current);
                    setShowAddMember(false);
                  }}
                  className="rounded-[6px] bg-[#1D9E75] px-3 py-[5px] text-[11px] text-[#E1F5EE] transition-opacity hover:opacity-90"
                >
                  + Задание группе
                </button>
              </div>
            </div>

            {detailLoading ? (
              <div className="flex min-h-[320px] animate-pulse flex-col gap-3 p-4">
                <div className="h-24 rounded-[6px] bg-[#ece7dd]" />
                <div className="h-32 rounded-[6px] bg-[#ece7dd]" />
                <div className="h-24 rounded-[6px] bg-[#ece7dd]" />
              </div>
            ) : (
              <div className="space-y-5 p-[14px]">
              {showAddMember ? (
                <div className="rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] p-3">
                  <div className="mb-2 flex items-center justify-between gap-3">
                    <div className="text-[11px] font-medium text-[#73726c]">
                      Добавить клиента
                      {selectedClientIds.length > 0 ? ` · выбрано ${selectedClientIds.length}` : ''}
                    </div>
                    <button
                      type="button"
                      onClick={() => void handleAddSelectedMembers()}
                      disabled={addingMembers || selectedClientIds.length === 0}
                      className="rounded-[6px] bg-[#1D9E75] px-3 py-[5px] text-[11px] text-[#E1F5EE] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {addingMembers ? 'Добавляю...' : 'Добавить выделенных'}
                    </button>
                  </div>
                  {availableClients.length === 0 ? (
                    <div className="text-[12px] text-[#73726c]">Все клиенты уже в группе</div>
                  ) : (
                    <div className="space-y-1">
                      {availableClients.map((client) => (
                        <div
                          key={client.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => toggleSelectedClient(client.id)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter' || event.key === ' ') {
                              event.preventDefault();
                              toggleSelectedClient(client.id);
                            }
                          }}
                          className={`flex w-full items-center gap-2 rounded-[6px] border-[0.5px] px-3 py-2 text-left transition-colors ${
                            selectedClientIds.includes(client.id)
                              ? 'border-[#1D9E75] bg-[#e1f5ee]'
                              : 'border-[#e0ddd6] bg-white hover:border-[#b4b2a9]'
                          }`}
                        >
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[#e1f5ee] text-[10px] font-medium text-[#0f6e56]">
                            {client.initials}
                          </div>
                          <span className="text-[12px] text-[#1a1a18]">{client.name}</span>
                          <span className="ml-auto truncate text-[10px] text-[#73726c]">{client.focus}</span>
                          <div
                            className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${
                              selectedClientIds.includes(client.id)
                                ? 'border-[#1D9E75] bg-[#1D9E75] text-white'
                                : 'border-[#d3d1c7] bg-white text-transparent'
                            }`}
                          >
                            ✓
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ) : null}

              <div>
                <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.4px] text-[#73726c]">
                  Участники
                </div>
                {detail.members.length === 0 ? (
                  <div className="text-[12px] text-[#73726c]">Участников пока нет</div>
                ) : (
                  <div className="space-y-[4px]">
                    {detail.members.map((member) => (
                      <div
                        key={member.clientId}
                        className="group/row flex items-center gap-2 rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white px-[10px] py-[7px]"
                      >
                        <div className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-full bg-[#e1f5ee] text-[10px] font-medium text-[#0f6e56]">
                          {member.initials}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-[12px] font-medium text-[#1a1a18]">{member.name}</div>
                          <div className="truncate text-[10px] text-[#73726c]">{member.focus}</div>
                        </div>
                        <div className="text-[10px] font-medium text-[#1D9E75]">{member.avgProgress}%</div>
                        <Link
                          href={`/coach/clients/${member.clientId}`}
                          className="ml-1 rounded-[4px] border-[0.5px] border-[#e0ddd6] px-[6px] py-[2px] text-[10px] text-[#73726c] opacity-0 transition-opacity hover:bg-[#f5f4f0] group-hover/row:opacity-100"
                        >
                          Открыть
                        </Link>
                        <button
                          type="button"
                          onClick={() => void handleRemoveMember(member.clientId)}
                          className="rounded-[4px] px-[6px] py-[2px] text-[10px] text-[#73726c] opacity-0 transition-opacity hover:bg-[#f5f4f0] group-hover/row:opacity-100"
                        >
                          ✕
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {showTaskForm ? (
                <div className="space-y-2 rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-[#f5f4f0] p-3">
                  <div className="text-[11px] font-medium text-[#73726c]">
                    Задание для всех {detail.members.length} участников
                  </div>
                  <textarea
                    value={taskText}
                    onChange={(event) => setTaskText(event.target.value)}
                    placeholder="Что должен сделать каждый участник группы..."
                    rows={2}
                    className="w-full resize-none rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-white px-[10px] py-2 text-[16px] leading-relaxed text-[#1a1a18] outline-none placeholder:text-[#73726c] focus:border-[#b4b2a9] sm:text-[12px]"
                  />
                  <div className="flex flex-wrap items-center gap-2">
                    <input
                      type="date"
                      value={taskDue}
                      onChange={(event) => setTaskDue(event.target.value)}
                      className="rounded-[6px] border-[0.5px] border-[#e0ddd6] bg-white px-[8px] py-[5px] text-[16px] text-[#73726c] outline-none focus:border-[#b4b2a9] sm:text-[11px]"
                    />
                    <span className="text-[10px] text-[#73726c]">срок (необязательно)</span>
                    <div className="flex-1" />
                    <button
                      type="button"
                      onClick={() => setShowTaskForm(false)}
                      className="rounded-[6px] border-[0.5px] border-[#d3d1c7] px-3 py-[5px] text-[11px] text-[#73726c] hover:bg-[#f5f4f0]"
                    >
                      Отмена
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleCreateTask()}
                      disabled={addingTask || !taskText.trim() || detail.members.length === 0}
                      className="rounded-[6px] bg-[#1D9E75] px-3 py-[5px] text-[11px] text-[#E1F5EE] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {addingTask ? 'Создаю...' : `Дать ${detail.members.length} участникам`}
                    </button>
                  </div>
                  {detail.members.length === 0 ? (
                    <div className="text-[10px] text-amber-600">Сначала добавьте участников в группу</div>
                  ) : null}
                </div>
              ) : null}

              <div>
                <div className="mb-2 text-[11px] font-medium uppercase tracking-[0.4px] text-[#73726c]">
                  Задания группе
                </div>
                {detail.tasks.length === 0 ? (
                  <div className="rounded-[8px] border-[0.5px] border-dashed border-[#e0ddd6] p-4 text-center text-[12px] text-[#73726c]">
                    Заданий пока нет, нажмите «+ Задание группе»
                  </div>
                ) : (
                  <div className="space-y-[4px]">
                    {detail.tasks.map((task) => {
                      const pct = task.totalCount > 0
                        ? Math.round((task.doneCount / task.totalCount) * 100)
                        : 0;
                      const allDone = task.totalCount > 0 && task.doneCount === task.totalCount;
                      const isOverdue = Boolean(task.dueDate) && !allDone && new Date(task.dueDate as string).getTime() < Date.now();

                      return (
                        <div
                          key={task.id}
                          className="group/task rounded-[8px] border-[0.5px] border-[#e0ddd6] bg-white px-[12px] py-[9px]"
                        >
                          <div className="flex items-start gap-2">
                            <div className="min-w-0 flex-1">
                              <div className="text-[12px] leading-relaxed text-[#1a1a18]">{task.text}</div>
                              <div className="mt-1 flex items-center gap-2">
                                <span
                                  className={`rounded-full px-[6px] py-[1px] text-[10px] ${
                                    allDone ? 'bg-[#E1F5EE] text-[#085041]' : 'bg-[#f1efe8] text-[#73726c]'
                                  }`}
                                >
                                  {task.doneCount} / {task.totalCount} выполнили
                                </span>
                                {task.dueDate ? (
                                  <span className={`text-[10px] ${isOverdue ? 'font-medium text-red-500' : 'text-[#73726c]'}`}>
                                    {isOverdue ? 'Просрочено · ' : 'до '}
                                    {formatDate(task.dueDate)}
                                  </span>
                                ) : null}
                              </div>
                            </div>
                            <button
                              type="button"
                              onClick={() => void handleDeleteTask(task.id)}
                              className="mt-0.5 shrink-0 rounded-[4px] px-[6px] py-[2px] text-[10px] text-[#73726c] opacity-0 transition-opacity hover:bg-[#f5f4f0] group-hover/task:opacity-100"
                            >
                              ✕
                            </button>
                          </div>
                          <div className="mt-2 h-[3px] overflow-hidden rounded-full bg-[#f1efe8]">
                            <div
                              className="h-full rounded-full transition-all"
                              style={{
                                width: `${pct}%`,
                                background: allDone ? '#1D9E75' : '#7F77DD',
                              }}
                            />
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
});

export default GroupsTab;

function formatDate(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return new Intl.DateTimeFormat('ru-RU', {
    day: 'numeric',
    month: 'long',
  }).format(date);
}
