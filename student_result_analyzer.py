# student result analyzer

print("\n------ Student Result ------")

student_name = input("Enter student name : ")
print("enter marks")
maths_marks = int(input("Maths : "))
english_marks = int(input("English : "))
science_marks = int(input("Science : "))

print("Total", (maths_marks+english_marks+science_marks))
f = (maths_marks+english_marks+science_marks)
percentage = float(f/3)
print("Percentage:", round(percentage, 2))

if(percentage >= 90):
    print("Outstanding Performance")


if (maths_marks >= 33 and english_marks >= 33 and science_marks >= 33):
    print("staus : pass")
    if(percentage >= 80):
        print("Grade = A")
    elif(percentage >= 60):
        print("Grade = B")
    elif(percentage >= 33):
        print("Grade = c")

else:
    print("status : fail")