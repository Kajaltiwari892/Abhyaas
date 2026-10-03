// Dated preparation guidance, not an eligibility decision. Review the source
// label and qualifications together when updating to another exam cycle.
export const examSource = {
  label: "CDS II 2026 notification",
  reviewed: "3 October 2026",
  notification: "https://www.upsc.gov.in/sites/default/files/Notif-CDS-II-2026-Engl-200526.pdf",
  examinations: "https://www.upsc.gov.in/examinations/active-exams",
};

export const academies = [
  {
    id: "ima", code: "IMA", name: "Indian Military Academy", service: "Indian Army",
    location: "Dehradun", commission: "Permanent Commission", papers: 3,
    education: "Recognised university degree or equivalent.",
    eligibilityNote: "Check the birth-date window and unmarried-male eligibility conditions in the notification.",
    photoAlt: "Chetwode Building at the Indian Military Academy, Dehradun",
  },
  {
    id: "ina", code: "INA", name: "Indian Naval Academy", service: "Indian Navy",
    location: "Ezhimala", commission: "Permanent Commission", papers: 3,
    education: "Engineering degree, or B.Sc. with Physics as a core/elective subject and Physics & Mathematics at 10+2, under the linked 2026 notice.",
    eligibilityNote: "Check the exact qualification, birth-date window and unmarried-male eligibility conditions for your cycle.",
    photoAlt: "Passing-out parade at the Indian Naval Academy, Ezhimala, in 2017",
  },
  {
    id: "afa", code: "AFA", name: "Air Force Academy", service: "Indian Air Force",
    location: "Dundigal", commission: "Permanent Commission", papers: 3,
    education: "Recognised degree with Physics & Mathematics at 10+2, or a Bachelor of Engineering.",
    eligibilityNote: "Check age, marital-status and flying-branch conditions, including any pilot-licence relaxation.",
    photoAlt: "Graduation parade at the Air Force Academy, Dundigal, in 2014",
  },
  {
    id: "ota", code: "OTA", name: "Officers Training Academy", service: "Indian Army",
    location: "Chennai", commission: "Short Service Commission", papers: 2,
    education: "Recognised university degree or equivalent.",
    eligibilityNote: "Men’s and women’s entries share the written papers; their age and marital-status conditions must be checked separately.",
    photoAlt: "Officers Training Academy campus in Chennai, photographed in 2023",
  },
] as const;

export type AcademyId = typeof academies[number]["id"];

export const writtenPapers = [
  { id: "english", name: "English", hint: "Comprehension, vocabulary & usage", marks: 100, hours: 2, ota: true },
  { id: "gk", name: "General Knowledge", hint: "History, geography, science & awareness", marks: 100, hours: 2, ota: true },
  { id: "maths", name: "Elementary Mathematics", hint: "Arithmetic, algebra, geometry & more", marks: 100, hours: 2, ota: false },
] as const;

export const photoCredits = [
  { label: "INA · Indian Navy, 2017", url: "https://commons.wikimedia.org/wiki/File:Passing_out_Parade_Spring_Term_2017_held_at_Indian_Naval_Academy,_Ezhimala_(2).jpg" },
  { label: "AFA · Ministry of Defence / PIB, 2014", url: "https://commons.wikimedia.org/wiki/File:The_Chief_of_the_Air_Staff,_Air_Chief_Marshal_Arup_Raha_reviewing_the_Graduation_Parade,_at_Air_Force_Academy,_Dundigal,_in_Hyderabad_on_June_21,_2014.jpg" },
  { label: "OTA · Army Training Command, 2023", url: "https://commons.wikimedia.org/wiki/File:OTA_Chennai.jpg" },
];
