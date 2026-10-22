# Project 1: NotesApp Threat Model and Risk Analysis

This is the shared group submission for Project 1 of the Computer Security course. This copy is maintained and submitted by **Chen Ziming (陈子明)**. The analysis and supporting files are group work.

**Submitting student's full name:** 陈子明 Chen Ziming

**CHU Student ID:** 2023905333

## Group members

Names are written in Chinese order: **family name first, given name second**. The Latin names below are Hanyu Pinyin without tone marks.

| Chinese name | Full name in Pinyin |
| --- | --- |
| 陈子明 | Chen Ziming |
| 高海天 | Gao Haitian |
| 吴彦澜 | Wu Yanlan |
| 叶与陈 | Ye Yuchen |

## Submission files

| Project requirement | File or worksheet |
| --- | --- |
| Numbered data-flow diagram with trust boundaries | [NotesApp-Numbered-DFD-English.pdf](NotesApp-Numbered-DFD-English.pdf) |
| STRIDE analysis covering all six categories | [NotesApp-STRIDE-English.xlsx](NotesApp-STRIDE-English.xlsx), **STRIDE and risk** |
| Likelihood × impact rating for each threat | The **L**, **I** and **Risk** columns in **STRIDE and risk** |
| Three priority risks and a fix for each | The **Top 3** worksheet in the same workbook |

Open the PDF first, then use its flow numbers to read the corresponding workbook rows. No application setup is needed to read these deliverables. A [Chinese study guide](README_STUDY.zh-CN.md) is also included.

## Scope and method

The analysis uses the course NotesApp source at commit [`1c83e422429c4b784411701ffd797b5ab5f397dc`](https://github.com/ziming-chen/NoteApp/tree/1c83e422429c4b784411701ffd797b5ab5f397dc). It concerns that classroom application, before the separate AES-GCM comment-encryption homework.

The diagram contains student, teacher and administrator browsers, the Flask application in Docker, and PostgreSQL. Its **16 numbered logical flows** cross two modeled trust boundaries:

- **TB1 — browser/application:** credentials, session tokens, form input, HTML, JSON and CSV pass between users and the web application.
- **TB2 — application/database:** SQL queries, updates and results pass between Flask and PostgreSQL.

The workbook assigns **one main threat to each flow**. Together, the 16 entries cover Spoofing, Tampering, Repudiation, Information disclosure, Denial of service and Elevation of privilege (STRIDE). Additional threats for the same flow are outside this first analysis.

Likelihood and impact each use **1 = low, 2 = medium, 3 = high**. For every entry, **risk = likelihood × impact**, producing scores from 1 to 9. The **Reason** column explains the rating. These are comparative judgments from source inspection, rather than measured attack probabilities. Risks involving intercepted HTTP traffic require access to remote traffic.

## Three priority risks

| Priority risk | Flow | L × I | Proposed fix |
| --- | --- | --- | --- |
| Login SQL injection | 1 | 3 × 3 = **9** | Use parameterized queries instead of placing login input directly into SQL. |
| Missing grade ownership checks | 6 | 3 × 3 = **9** | Restrict student reads to their own records and teacher operations to their assigned classes. Enforce these checks on the server. |
| Unsafe JWT verification | 2 | 3 × 3 = **9** | Require a valid signature, a strong signing secret and an expiration time. Reject unsigned or invalid tokens. |

Flows **1, 2, 5, 6 and 14** all score 9. Flows 5, 6 and 14 reflect the same missing ownership controls, so the priority list groups that cause instead of counting it three times. The scores are not added together.

## Evidence and limits

The threat descriptions and ratings are based on reading the application code. They are possible risks, not results from exploitation or load testing. The fixes above are recommendations; they have not been implemented or verified as part of this Project 1 submission. This report does not claim that the application is secure.

The PDF and workbook are the shared group deliverables, also published in the [group's other submission copy](https://github.com/Viclant/NoteApp/tree/main/project1). This repository preserves them unchanged and provides the group details and explanation for Chen Ziming's submission copy.

The course brief specifies a GitHub hand-in before **20 October 2026** and a **three-minute presentation per group on 20 October**. The presentation is separate from these repository files.
