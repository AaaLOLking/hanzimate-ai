"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { apiRequest, type Course, type LessonDetail } from "@/lib/api";

export default function CoursesPage() {
  const router = useRouter();
  const [courses, setCourses] = useState<Course[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [startingId, setStartingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest<Course[]>("/api/v1/courses")
      .then((catalog) => {
        if (!cancelled) setCourses(catalog);
      })
      .catch((requestError) => {
        if (!cancelled) {
          setError(requestError instanceof Error ? requestError.message : "课程目录加载失败");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function openLesson(lessonId: string) {
    setStartingId(lessonId);
    setError("");
    try {
      await apiRequest<LessonDetail>(`/api/v1/lessons/${lessonId}/start`, {
        method: "POST",
      });
      router.push(`/lessons/${lessonId}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "课程启动失败");
      setStartingId(null);
    }
  }

  return (
    <AppShell active="courses">
      <section className="courseCatalogHero">
        <span className="sectionLabel">SYSTEMATIC COURSES</span>
        <h1>把知识变成能用出来的中文</h1>
        <p>短解释、对比例句、无提示提取、真实迁移。只有产出证据通过，课程才算完成。</p>
      </section>
      <section className="courseCatalogContent">
        {error ? <p className="reportError" role="alert">{error}</p> : null}
        {loading ? <p className="courseLoading">正在读取课程版本…</p> : null}
        {courses.map((course) => {
          const completed = course.lessons.filter(
            (lesson) => lesson.progress?.status === "completed",
          ).length;
          return (
            <article className="courseCollection reveal" key={`${course.id}-${course.version}`}>
              <div className="courseCollectionIntro">
                <div>
                  <span className="sectionLabel">{course.framework}</span>
                  <h2>{course.title}</h2>
                  <p>{course.description}</p>
                </div>
                <div className="courseCompletion">
                  <strong>{completed}/{course.lessons.length}</strong>
                  <span>课程完成</span>
                </div>
              </div>
              <div className="courseLessonList">
                {(["daily-life", "hsk"] as const).map((track) => {
                  const lessons = course.lessons.filter((lesson) => lesson.track === track);
                  if (lessons.length === 0) return null;
                  return (
                    <section className="courseTrack" key={track}>
                      <div className="courseTrackHeading">
                        <span>{track === "daily-life" ? "LIFE IN CHINA" : "HSK SKILLS"}</span>
                        <strong>{track === "daily-life" ? "生活与校园沟通" : "考试能力训练"}</strong>
                        <em>{lessons.length} 节</em>
                      </div>
                      {lessons.map((lesson) => (
                        <section className="courseLessonRow" key={lesson.id}>
                          <div className="lessonIndex">
                            {String(lesson.position).padStart(2, "0")}
                          </div>
                          <div className="lessonCatalogCopy">
                            <div>
                              <span>{lesson.level}</span>
                              <span>{lesson.estimated_minutes} 分钟</span>
                            </div>
                            <h3>{lesson.title}</h3>
                            <p>{lesson.objective}</p>
                            <div className="lessonTargetTags">
                              {lesson.targets.slice(0, 4).map((target) => (
                                <span key={target}>{target}</span>
                              ))}
                            </div>
                          </div>
                          <div className="lessonCatalogAction">
                            {lesson.progress ? (
                              <span className={`lessonProgressState ${lesson.progress.status}`}>
                                {lesson.progress.status === "completed"
                                  ? "已完成"
                                  : `第 ${lesson.progress.current_step + 1}/3 步`}
                              </span>
                            ) : <span className="lessonProgressState">未开始</span>}
                            <button
                              disabled={startingId === lesson.id}
                              onClick={() => void openLesson(lesson.id)}
                            >
                              {startingId === lesson.id
                                ? "正在打开…"
                                : lesson.progress?.status === "completed"
                                  ? "查看课件"
                                  : lesson.progress
                                    ? "继续学习"
                                    : "开始本课"}
                            </button>
                          </div>
                        </section>
                      ))}
                    </section>
                  );
                })}
              </div>
              <footer className="courseVersionNote">
                课程版本 v{course.version} · 发布后不可覆盖 · 原创练习依据官方标准编写
              </footer>
            </article>
          );
        })}
      </section>
    </AppShell>
  );
}
