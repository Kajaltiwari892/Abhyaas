// Dated preparation guidance, not an eligibility decision. Review the source
// label and qualifications together when updating to another exam cycle.
export const examSource = {
  label: "CDS II 2026 notification",
  reviewed: "7 October 2026",
  notification: "https://www.upsc.gov.in/sites/default/files/Notif-CDS-II-2026-Engl-200526.pdf",
  examinations: "https://www.upsc.gov.in/examinations/active-exams",
};

export const academies = [
  {
    id: "ima", code: "IMA", name: "Indian Military Academy", service: "Indian Army",
    location: "Dehradun", commission: "Permanent Commission", papers: 3,
    education: "Recognised university degree or equivalent.",
    entry: "Men only", age: "19–24 years",
    birthDates: "Born between 1 July 2003 and 1 July 2008, including both dates.",
    menEligibility: "Unmarried men can apply.",
    womenEligibility: "This CDS entry is for men. Women can apply to OTA.",
    photoAlt: "Chetwode Building at the Indian Military Academy, Dehradun",
  },
  {
    id: "ina", code: "INA", name: "Indian Naval Academy", service: "Indian Navy",
    location: "Ezhimala", commission: "Permanent Commission", papers: 3,
    education: "Engineering degree, or B.Sc. with Physics as a core or elective subject and Physics & Mathematics in Class 12.",
    entry: "Men only", age: "19–24 years",
    birthDates: "Born between 1 July 2003 and 1 July 2008, including both dates.",
    menEligibility: "Unmarried men can apply.",
    womenEligibility: "This CDS entry is for men. Women can apply to OTA.",
    photoAlt: "Passing-out parade at the Indian Naval Academy, Ezhimala, in 2017",
  },
  {
    id: "afa", code: "AFA", name: "Air Force Academy", service: "Indian Air Force",
    location: "Dundigal", commission: "Permanent Commission", papers: 3,
    education: "Recognised university degree with Physics & Mathematics in Class 12, or a Bachelor of Engineering.",
    entry: "Men only", age: "20–24 years on 1 July 2027",
    birthDates: "Born between 1 July 2003 and 1 July 2007, including both dates.",
    menEligibility: "Men under 25 must be unmarried. A valid DGCA Commercial Pilot Licence raises the upper age limit to 26; see the notice for the conditions.",
    womenEligibility: "This CDS entry is for men. Women can apply to OTA.",
    photoAlt: "Graduation parade at the Air Force Academy, Dundigal, in 2014",
  },
  {
    id: "ota", code: "OTA", name: "Officers Training Academy", service: "Indian Army",
    location: "Chennai", commission: "Short Service Commission", papers: 2,
    education: "Recognised university degree or equivalent.",
    entry: "Men & women", age: "19–25 years",
    birthDates: "Born between 1 July 2002 and 1 July 2008, including both dates.",
    menEligibility: "Unmarried men can apply.",
    womenEligibility: "Unmarried women can apply. Widows and divorced women can also apply if they have no children and have not remarried; divorced applicants need divorce documents.",
    photoAlt: "Officers Training Academy campus in Chennai, photographed in 2023",
  },
] as const;

export function getAcademyGuide(id: AcademyId) {
  const academy = academies.find((item) => item.id === id)!;
  const papers = writtenPapers.filter((paper) => id !== "ota" || paper.ota);
  return {
    academy,
    papers,
    writtenMarks: papers.reduce((total, paper) => total + paper.marks, 0),
    writtenHours: papers.reduce((total, paper) => total + paper.hours, 0),
  };
}

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
